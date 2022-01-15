from jinja2 import Environment, FileSystemLoader, nodes
from jinja2.ext import Extension
from jinja2.parser import Parser
from jinja2.runtime import Macro
import re
from typing import Dict, Any, Optional
from pathlib import Path
from os import walk
from gadfly.config import Config
from gadfly.cli import info, colors
from gadfly.utils import output_path
from gadfly.page_hooks_api import *
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


def compile_page(page: Path, config: Config, env: Environment, page_vars: Optional[Dict] = None):
    """Generate HTML output from page.

    Args:
        page: path to the page file (.md) with the content
        config: gadfly config
        env: Jinja2 environment
        page_vars: additional variables to make available to the templating environment for this page only.

    Returns:
        the generated HTML output as a string
    """
    with open(page.absolute()) as fh:
        page_source = fh.read()
    # Enrich context with page-specific vars
    page_name = page.relative_to(config.pages_path)

    def md_assoc(**kwargs) -> str:
        config.page_md[page_name] = {**config.page_md[page_name], **kwargs}
        return ""  # if None is returned, None is rendered in the output iff function is called directly

    template = env.from_string(page_source)
    if page_vars:
        template.globals.update(**page_vars)
    template.globals.update({"gf_page_name": page_name, "gf_md_assoc": md_assoc})
    res = template.render(config.context)
    return re.sub("(^<P>|</P>$)", "", res, flags=re.IGNORECASE)


def write_output_file(config: Config, page_path: Path, content: str):
    out_path = output_path(config, page_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as fh:
        info(f"'{colors.B_MAGENTA}{page_path.relative_to(config.project_root)}{colors.B_WHITE}' -> '{colors.B_MAGENTA}{out_path.relative_to(config.project_root)}{colors.B_WHITE}'")
        fh.write(content)


def unlink_output_file(config: Config, page_path: Path):
    out_path = output_path(config, page_path)
    out_path.unlink(missing_ok=True)
    page_dir = out_path.parent
    if page_dir.exists():
        out_path.parent.rmdir()


def render(config: Config, env: Environment, page_path: Path,
           page_pre_compile_hook: PagePreCompileHookFn,
           page_post_compile_hook: PagePostCompileHookFn) -> None:
    # clear page metadata before compilation
    config.page_md[page_path.relative_to(config.pages_path)] = {}

    # call per-page pre-compile hook, can create extra vars to inject into the template-rendering
    # context for this page, cause compilation to be skipped and set page metadata (if desired)
    extra_vars = {}
    if not page_pre_compile_hook(page_path, config, extra_vars):
        # filtered out, abort
        unlink_output_file(config, page_path)
        config.page_md[page_path.relative_to(config.pages_path)] = {}
        return

    content = compile_page(page_path, config, env, page_vars=extra_vars)

    content = page_post_compile_hook(page_path, config, content)
    if content in (False, None):
        # filtered out, abort
        # clear out any MD that might have been set as part of the compilation
        unlink_output_file(config, page_path)
        config.page_md[page_path.relative_to(config.pages_path)] = {}
        return

    write_output_file(config, page_path, content)


def render_all(config: Config, env: Environment,
               page_pre_compile_hook: PagePreCompileHookFn,
               page_post_compile_hook: PagePostCompileHookFn) -> None:
    for dirpath, _dir_names, file_names in walk(config.pages_path):
        for file_name in file_names:
            if file_name.endswith(".md"):
                page_path = Path(dirpath) / file_name
                render(config, env, page_path, page_pre_compile_hook, page_post_compile_hook)
