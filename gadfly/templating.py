from typing import Optional, Dict, Any, List, Union
from pathlib import Path
from io import StringIO
from mako.runtime import Context, TemplateNamespace
from mako.template import Template
from mako.lookup import TemplateLookup
from gadfly.config import Config
from re import (
    compile as re_compile,
    split as re_split,
    MULTILINE as RE_MULTILINE)

# <%= EXPR %>   --- supports multiline, not sure how useful that is.

# supports inline python, multiple lines
# (! DOES NOT SUPPORT '%>' being present anywhere in the code block --- perhaps remove this stx for '%% py' )
# <% STATEMENTS... %>

# supports BLOCKS
# WHITESPACE* '%%' WHITESPACE* '/'? BLOCK_IDENTIFIER (WHITESPACE+ (WHITESPACE|ANY_CHAR))
# So '%% py' {"block": "py", args: ""}
# and '%% foo something else -> {"block": "foo", "args": "something else"}
rgx_template_tokens = re_compile(
    r"(<%=[\s\S]*?\%\>|<%[\s\S]*?\%\>|^[ \t\r\f\v]*%%[ \t\r\f\v]*/?[a-zA-Z]\w*(?:[ \t\r\f\v]+[ \t\r\f\v\S]*)?$)",
    RE_MULTILINE
)


def tokenize(template_source: str) -> List[str]:
    return re_split(rgx_template_tokens, template_source)


class CodeBuilder:
    code: List[Union[str, "CodeBuilder"]]
    indent_level: int
    indent_step: int

    def __init__(self, indent_step=4):
        self.code = []
        if indent_step <= 0:
            raise ValueError("indentation step must be a positive number")
        self.indent_step = indent_step
        self.__indent_level = 0

    def __str__(self) -> str:
        return "".join(str(c) for c in self.code)

    @property
    def indent_level(self) -> int:
        return self.__indent_level

    def add_line(self, line) -> None:
        self.code.extend([
            " " * self.indent_level,
            line,
            "\n"
        ])

    def add_section(self) -> "CodeBuilder":
        section = CodeBuilder(indent_step=self.indent_step)
        section.__indent_level = self.indent_level

        self.code.append(section)
        return section

    def indent(self) -> None:
        self.__indent_level += self.indent_step

    def dedent(self) -> None:
        new_indent = self.indent_level - self.indent_step
        if new_indent < 0:
            raise ValueError("cannot dedent - indentation level would be negative!")
        self.__indent_level = new_indent

    def eval(self) -> Dict[str, Any]:
        """Evaluate code and return top-level definitions.

        Returns:
            Dictionary of top-level variable definitions.
        """
        # ensure top-level is being evaluated
        assert self.indent_level == 0

        py_src = str(self)
        global_ns = {}
        exec(py_src, global_ns)
        return global_ns


class TemplateSyntaxError(ValueError):
    def __init__(self, msg: str, thing: Any):
        self.msg = msg
        self.thing = thing
        super().__init__(f"{msg}: {repr(thing)}")


class TTemplate:
    """A template-renderer pining for the simpler days."""
    def __init__(self, source, *contexts: Dict[str, Any]):
        """Construct template from `source`."""

        # construct context from successively merging each given context dict
        self.context = {}
        for context in contexts:
            self.context.update(context)

        # TODO: explain
        self._all_vars = set()
        self._loop_vars = set()

        self._code = CodeBuilder()
        code = self._code

        code.add_line("def render_function(context):")
        code.indent()
        vars_code = code.add_section()
        code.add_line("result = []")

        # local aliases to reduce lookup overhead
        code.add_line("append_result = result.append")
        code.add_line("extend_result = result.extend")
        code.add_line("to_str = str")

        # TODO: explain
        buffered = []

        def flush_output():
            """Force `buffered` to the code builder."""
            if len(buffered) == 1:
                code.add_line(f"append_result({buffered[0]})")
            elif len(buffered) > 1:
                code.add_line(f"""extend_result([{", ".join(buffered)}])""")
            del buffered[:]

        # TODO: explain
        ops_stack = []

        tokens = tokenize(source)

        for token in tokens:
            if token.startswith("<%="):
                # expression, eval and write to output
                expr_code = token[3:-2].strip()
                buffered.append(f"""to_str(eval({repr(expr_code)}, context))""")
            elif token.startswith("<%"):
                flush_output()
                code_block = token[2:-2].strip()
                code.add_line(f"""exec({(repr(code_block))}, context)""")
            elif token.startswith("%%"):
                flush_output()
                block_name = token[2:].strip()
                block_content = []
                for token in tokens:
                    if token.startswith("%%"):
                        token_name = token[2:].strip()
                        if token_name[0] == "/" and token_name[1:] == block_name:
                            # found end of block, send content to handler, eval
                            # TODO: implement
                            code.add_line(f"""print({repr(block_name)})""")
                            break
                    block_content.append(token)
                code.add_line(f"""eval_block({repr(block_name)}, {repr(block_content)})""")
            else:
                # literal content, write it out
                if token:
                    buffered.append(repr(token))

        if ops_stack:
            raise TemplateSyntaxError(
                "Unmatched block tag", ops_stack[-1]
            )

        flush_output()

        # TODO: explain
        for var_name in self._all_vars - self._loop_vars:
            vars_code.add_line(f"c_{var_name} = context[{repr(var_name)}]")

        code.add_line("""return "".join(result)""")
        code.dedent()
        self._render_function = code.eval()["render_function"]

    def render(self, context: Optional[Dict[str, Any]] = None):
        """Render template."""
        render_context = {**self.context, **(context or {})}
        return self._render_function(render_context)


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
        self._prelude_template = prelude_ns()
        pass

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


def prelude_ns() -> Template:
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


# mako.runtime.py, _populate_self_namespace
def install_ns(context: Context, template: Template, ns: str):
    tns = TemplateNamespace(
        ns,
        context,
        template=template,
        populate_self=False,
    )
    context._data[ns] = tns

