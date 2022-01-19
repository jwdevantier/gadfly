from enum import Enum
from typing import List, Union, Dict, Any, Optional, Generator, Callable, Tuple
from re import (
    compile as re_compile,
    match as re_match,
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
    r"(<%=[\s\S]*?\%\>|<%[\s\S]*?\%\>|^[ \t\r\f\v]*%%[ \t\r\f\v]*/?[a-zA-Z].*$\n?)",
    RE_MULTILINE
)

# name: the block identifier
# args: None  OR whatever's between the outermost (), so '()' => '' and (x, y) => 'x, y'
rgx_block_open = r"^[ \t\r\f\v]*%%[ \t\r\f\v]*(?P<name>/?[a-zA-Z]\w*)(?:\((?P<args>.*)\))?$"


def _eval_args_str(args: str, ctx) -> Tuple[List[Any], Dict[str, Any]]:
    code = f"""\
def get_args(*args, **kwargs):
    return (args, kwargs)

_it = get_args({args})
"""
    tmp_ctx = {**ctx}
    exec(code, tmp_ctx)
    args, kwargs = tmp_ctx["_it"]
    return list(args), kwargs


class Tokenizer:
    # list/slice of tokens
    _tokens: List[str]
    # current position of tokenizer in list of tokens
    _pos: int

    def __init__(self):
        self._pos = 0

    @staticmethod
    def from_source(source: str) -> "Tokenizer":
        t = Tokenizer()
        t._tokens = re_split(rgx_template_tokens, source)
        return t

    def copy(self) -> "Tokenizer":
        """Creates lightweight/shallow copy over token stream."""
        t = Tokenizer()
        t._tokens = self._tokens[self._pos:]
        t._pos = self._pos
        return t

    # support copy.copy
    __copy__ = copy

    def peek(self) -> str:
        """Get current token without advancing"""
        return self._tokens[self._pos]

    def next(self) -> str:
        """Advance by one token"""
        pos = self._pos
        self._pos = pos + 1
        return self._tokens[pos]

    def has_more(self) -> bool:
        """True iff. there are more tokens to parse"""
        return self._pos < len(self._tokens)

    def __str__(self):
        return f"""Tokenizer<pos: {self._pos}, len: {len(self._tokens)}>"""


class TokenType(Enum):
    TEXT = 0
    BLOCK = 1
    PY_EXPR = 2
    PY_BLOCK = 3

    def __repr__(self):
        return str(self.name)


def cst_build(tokenizer: Tokenizer) -> list:
    ast_stack = []
    current = []
    while tokenizer.has_more():
        token = tokenizer.next()
        if token.startswith("<%="):
            current.append([TokenType.PY_EXPR, token])
        elif token.startswith("<%"):
            current.append([TokenType.PY_BLOCK, token])
        elif token.startswith("%%"):
            m = re_match(rgx_block_open, token)
            if not m:
                raise ValueError(f"syntax error in block tag: {repr(token)}")
            name = m.group("name")
            args = m.group("args")

            if not name.startswith("/"):
                # new block, push current block to stack
                ast_stack.append(current)
                current = [TokenType.BLOCK,
                           [name, args.strip()] if (args and args.strip() != "") else [name],
                           token]
            else:
                # end of block, but is it the right one?
                if name[1:] != current[1][0]:
                    raise ValueError(f"expected {repr(current[1][0])}, got {repr(name)}")
                current.append(token) # append END (to maintain CST)
                child = current
                current = ast_stack.pop()
                current.append(child)
        else:
            current.append([TokenType.TEXT, token])
    if ast_stack:
        raise ValueError(f"stack should be empty, is {repr(ast_stack)}")

    return current


def cst_flatten(cst: list) -> Generator[str, None, None]:
    if len(cst) == 0:
        return

    if isinstance(cst[0], TokenType):
        ntype = cst[0]
        if ntype == TokenType.BLOCK:
            yield cst[2]  # yield open line
            yield from cst_flatten(cst[3:-1])  # yield from children
            yield cst[-1]  # yield close line
        elif ntype in (TokenType.TEXT, TokenType.PY_BLOCK, TokenType.PY_EXPR):
            yield cst[1]
        else:
            raise ValueError(f"unknown token type {repr(ntype)}")
    else:
        # top-level (~PROGN) or body of some block
        for elem in cst:
            yield from cst_flatten(elem)


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


CompileCSTFn = Callable[[list], None]
BlockCompilerFn = Callable[[str, List[Any], Dict[str, Any], list], list]


def block_compile_py(name: str,
                     args: List[Any],
                     kwargs: Dict[str, Any],
                     body_cst: list) -> list:
    assert len(body_cst) == 1, f"""malformed body input {repr(body_cst)}"""
    assert body_cst[0][0] == TokenType.TEXT, "expected text node"
    _, code = body_cst[0]
    return [TokenType.PY_BLOCK,
            f"<% {code} %>"]


def block_compile_doc(name: str,
                      args: List[Any],
                      kwargs: Dict[str, Any],
                      body_cst: list) -> list:
    # doc blocks are just for documenting the template, no processing needed
    pass


class Template:
    def __init__(self,
                 cst: list,
                 *contexts: Dict[str, Any],
                 macros: Optional[Dict[str, BlockCompilerFn]] = None):
        # construct context from successively merging each given context dict
        self.__compile_time_context = {}
        for context in contexts:
            self.__compile_time_context.update(context)

        self._code = CodeBuilder()
        # use this to store/buffer output until required to flush it out (using `flush_output`)
        # this reduces the amount of code generated in the resulting render function
        self.__output_buffer = []
        self.__macros = macros

        code = self._code
        code.add_line("def render_function(context):")
        code.indent()
        code.add_line("result = []")

        # local aliases to reduce lookup overhead
        code.add_line("append_result = result.append")
        code.add_line("extend_result = result.extend")
        code.add_line("to_str = str")

        # TODO: this approach will lose the ability to insert a CodeBuilder
        #       as a point of later extension UNLESS we alter things somehow
        #       (but do we need it?)
        if len(cst) == 0:
            raise ValueError("program cannot be empty")

        self.__compile_body(
            cst if isinstance(cst[0], list) else [cst]
        )
        self.__flush_output()
        code.add_line("""return "".join(result)""")
        code.dedent()
        self._render_function = code.eval()["render_function"]

    def __compile_body(self, body: list):
        stack = []
        current = body
        for node in current:
            ntype = node[0]
            if isinstance(ntype, list):
                stack.append(current)
                current = node
            elif ntype == TokenType.TEXT:
                txt = node[1]
                if txt:
                    self.__output_buffer.append(repr(txt))
            elif ntype == TokenType.PY_EXPR:
                expr_code = node[1][3:-2].strip()
                self.__output_buffer.append(
                    f"""to_str(eval({repr(expr_code)}, context))"""
                )
            elif ntype == TokenType.PY_BLOCK:
                self.__flush_output()
                code_block = node[1][2:-2].strip()
                self._code.add_line(
                    f"""exec({repr(code_block)}, context)"""
                )
            elif ntype == TokenType.BLOCK:
                # BLOCK: [<TYPE> <HEADER> <RAW HEADER> BODY... <RAW END>]
                # where HEADER: [<name>, <args>]
                name = node[1][0]
                args = node[1][1] if len(node[1]) == 2 else None
                if args:
                    # evaluating with macro-time context only.
                    args, kwargs = _eval_args_str(args, self.__compile_time_context)
                else:
                    args = []
                    kwargs = {}
                body = node[3:-1]

                # locate appropriate compiler and pass control to it
                macro = self.__macros.get(name)
                if not macro:
                    raise ValueError(f"unknown block type {repr(name)}")

                expanded_cst = macro(name, args, kwargs, body)
                if expanded_cst:
                    if not isinstance(expanded_cst[0], list):
                        expanded_cst = [expanded_cst]
                    self.__flush_output()  # TODO: do we even need this ?
                    try:
                        self.__compile_body(expanded_cst)
                    except Exception as e:
                        print("expanded cst")
                        print(repr(expanded_cst))
                        print("error")
                        print(str(e))
                        raise e
            else:
                raise TemplateSyntaxError("unexpected element in state __compile_node", node)

    def __flush_output(self):
        """Force `buffered` to the code builder."""
        if len(self.__output_buffer) == 1:
            self._code.add_line(f"append_result({self.__output_buffer[0]})")
        elif len(self.__output_buffer) > 1:
            self._code.add_line(f"""extend_result([{", ".join(self.__output_buffer)}])""")
        del self.__output_buffer[:]

    def render(self, context: Optional[Dict[str, Any]] = None):
        render_context = {**self.__compile_time_context, **(context or {})}
        return self._render_function(render_context)
