from jinja2 import Environment, FileSystemLoader, nodes
from jinja2.ext import Extension
from jinja2.parser import Parser
from jinja2.runtime import Macro
import re
from typing import Dict, Any
from pathlib import Path
from os import walk
from gadfly.config import Config
from gadfly.utils import info
from markdown_it import MarkdownIt

md = MarkdownIt()


class MDExt(Extension):
    tags = {"md", "markdown"}  # "markdown"

    def __init__(self, environment: Environment):
        super().__init__(environment)

    def parse(self, parser: Parser):
        tok = next(parser.stream)
        lineno = tok.lineno
        endtok = "name:endmd" if tok.value == "md" else "name:endmarkdown"
        body = parser.parse_statements((endtok,), drop_needle=True)
        return nodes.CallBlock(
            self.call_method("_render_markdown"),
            [], [], body
        ).set_lineno(lineno)

    def _render_markdown(self, caller: Macro):
        block = caller()
        return md.render(block).strip()


j2loader = FileSystemLoader(searchpath="./templates")
j2env = Environment(
    loader=j2loader,
    auto_reload=True,
    autoescape=False,
    extensions=[MDExt]
)

Context = Dict[str, Any]


def page_path(config: Config, output_path: Path) -> Path:
    if not output_path.suffix == ".html":
        raise RuntimeError("expected html file")
    fpath = output_path.relative_to(config.output_path)
    if fpath.name == "index.html":
        fpath = Path(*fpath.parts[:-2]) / (fpath.parts[-2] + ".md")
    else:
        fpath = fpath.parent / (fpath.name[:-len(fpath.suffix)] + ".md")
    fpath = config.pages_path / fpath
    return fpath


def output_path(config: Config, page_path: Path) -> Path:
    if not page_path.suffix == ".md":
        raise RuntimeError("expected markdown file")
    fpath = page_path.relative_to(config.pages_path)
    return config.output_path / fpath.parent / (fpath.name[:-len(".md")]) / "index.html"


def compile_page(page: Path, context: Context):
    with open(page.absolute()) as fh:
        page_source = fh.read()
    res = j2env.from_string(page_source).render(**context)
    return re.sub("(^<P>|</P>$)", "", res, flags=re.IGNORECASE)


def compile_all(config: Config):
    for dirpath, dir_names, file_names in walk(config.pages_path):
        for filename in file_names:
            if filename.endswith(".md"):
                fpath = (Path(dirpath) / filename)
                yield fpath, compile_page(fpath, config.context)


def write_output_file(config: Config, page_path: Path, content: str):
    out_path = output_path(config, page_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as fh:
        info(f"{page_path.relative_to(config.project_root)} -> {out_path.relative_to(config.project_root)}")
        fh.write(content)


def render(config: Config, page: Path):
    content = compile_page(page, config.context)
    write_output_file(config, page, content)


def render_all(config: Config):
    for page_path, content in compile_all(config):
        write_output_file(config, page_path, content)
