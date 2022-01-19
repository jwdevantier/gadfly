from typing import Optional, Dict, Any
from pathlib import Path
from io import StringIO
from mako.runtime import Context, TemplateNamespace
from mako.template import Template
from mako.lookup import TemplateLookup
from gadfly.config import Config


class Environment:
    def __init__(self, config: Config, module_directory: Optional[Path] = None):
        # ensure we have directory to cache compiled templates
        # TODO: each compile process creates a new dir...
        # if module_directory is None:
        #     tmp = tempfile.NamedTemporaryFile()
        #     module_directory = Path(tmp.name)
        #     tmp.close()
        #     module_directory.mkdir(parents=True)
        #
        # self.module_directory = module_directory
        self._config = config
        self._lookup = TemplateLookup(directories=[config.templates_path])
        self._prelude_template = self.__prelude_ns()

    def __prelude_ns(self) -> Template:
        return Template("""<%!
from markdown_it import MarkdownIt

def to_markdown(fn):
    def decorate(context, *args, **kwargs):
        out = runtime.capture(context, fn, *args, **kwargs)
        return MarkdownIt().render(out).strip()
    return decorate

%>
<%def name="markdown()" decorator="to_markdown">
${caller.body()}
</%def>""")

    def template_from_file(self, file_path: Path) -> Template:
        # return Template(filename=str(file_path.absolute()),
        #                 module_directory=self.module_directory)
        return Template(
            filename=str(file_path.absolute()),
            lookup=self._lookup
        )

    def render(self, template: Template, render_ctx: Dict[str, Any]) -> str:
        buf = StringIO()
        mako_ctx = Context(buf, **{
            **self._config.context,
            **render_ctx
        })
        prelude_ns = TemplateNamespace(
            "gadfly",
            mako_ctx,
            template=self._prelude_template,
            populate_self=False
        )
        mako_ctx._data["gadfly"] = prelude_ns
        # template.render_context(mako_ctx, **{**self._config.context, **render_ctx})
        template.render_context(mako_ctx)
        return buf.getvalue()
        # return template.render(**{**self._config.context, **render_ctx})
