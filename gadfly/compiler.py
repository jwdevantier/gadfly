from jinja2 import Environment, FileSystemLoader, nodes
from jinja2.ext import Extension
from jinja2.parser import Parser
from jinja2.runtime import Macro
import re
from typing import Dict, Any
from pathlib import Path
from os import walk
from gadfly.config import Config
from gadfly.cli import info, colors
from gadfly.utils import output_path
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


def get_j2env(config: Config) -> Environment:
    j2loader = FileSystemLoader(searchpath=config.templates_path)
    return Environment(
        loader=j2loader,
        auto_reload=True,
        autoescape=False,
        extensions=[MDExt]
    )


Context = Dict[str, Any]


def render_generated_page(page: Path, template: str, cfg: Config, env: Environment, ctx: Context):
    """Generate page from path, template and given context."""
    if page.is_absolute():
        try:
            # is_relative_to requires Python 3.9
            page.relative_to(cfg.output_path)
        except AttributeError:
            # TODO: better error
            raise RuntimeError(f"invalid path '{page}' - not contained in output_path")
    else:
        page = cfg.output_path / page
    # find template
    # TODO: error-check
    template = env.get_template(template)
    content = template.render(**{**cfg.context, **ctx})
    page.parent.mkdir(parents=True, exist_ok=True)
    with open(page, "w") as fh:
        info(f"generating page '{colors.B_MAGENTA}{page.relative_to(cfg.project_root)}{colors.B_WHITE}'")
        fh.write(content)


def compile_page(page: Path, config: Config, env: Environment):
    with open(page.absolute()) as fh:
        page_source = fh.read()
    # Enrich context with page-specific vars
    page_name = page.relative_to(config.pages_path)
    config.page_md[page_name] = {}

    def md_assoc(**kwargs) -> str:
        config.page_md[page_name] = {**config.page_md[page_name], **kwargs}
        return ""  # if None is returned, None is rendered in the output iff function is called directly

    template = env.from_string(page_source)
    template.globals.update({"gf_page_name": page_name, "gf_md_assoc": md_assoc})
    res = template.render(config.context)
    return re.sub("(^<P>|</P>$)", "", res, flags=re.IGNORECASE)


def compile_all(config: Config, env: Environment):
    for dirpath, dir_names, file_names in walk(config.pages_path):
        for filename in file_names:
            if filename.endswith(".md"):
                fpath = (Path(dirpath) / filename)
                yield fpath, compile_page(fpath, config, env)


def write_output_file(config: Config, page_path: Path, content: str):
    out_path = output_path(config, page_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as fh:
        info(f"'{colors.B_MAGENTA}{page_path.relative_to(config.project_root)}{colors.B_WHITE}' -> '{colors.B_MAGENTA}{out_path.relative_to(config.project_root)}{colors.B_WHITE}'")
        fh.write(content)


def render(config: Config, env: Environment, page: Path):
    content = compile_page(page, config, env)
    write_output_file(config, page, content)


def render_all(config: Config, env: Environment):
    for page_path, content in compile_all(config, env):
        write_output_file(config, page_path, content)
