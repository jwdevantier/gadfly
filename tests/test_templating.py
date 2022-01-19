from gadfly.templating import *
import pytest


def test_tokenizer():
    x = Tokenizer.from_source("""
hello world
<% code time %>

<%
much
more
code
%>

something else

<%= foo() %>

%% py
%% /py
""")
    assert x._tokens == [
        "\nhello world\n",
        "<% code time %>",
        "\n\n",
        "<%\nmuch\nmore\ncode\n%>",
        "\n\nsomething else\n\n",
        "<%= foo() %>",
        "\n\n",
        "%% py\n",
        "",
        "%% /py\n",
        ""
    ]


@pytest.mark.parametrize("ast, tokens", [
    ([], []),
    ([TokenType.TEXT, "hello, world\n"],
     ["hello, world\n"]),
    ([TokenType.PY_EXPR, "<%= name %>"],
     ["<%= name %>"]),
    ([TokenType.PY_BLOCK, "<%\nprint(3.14)\nprint(foo)\n%>"],
     ["<%\nprint(3.14)\nprint(foo)\n%>"]),
    ([TokenType.BLOCK, ["py"], "%% py",
      [TokenType.TEXT, "print(2 + x)"],
      "%% /py"],
     ["%% py", "print(2 + x)", "%% /py"]),
    ([[TokenType.TEXT, "Hello, "],
      [TokenType.PY_BLOCK, """<% print("Mr. ") %>"""],
      [TokenType.PY_EXPR, "<%= name %>"],
      [TokenType.TEXT, "!"]],
     ["Hello, ", """<% print("Mr. ") %>""", "<%= name %>", "!"])
])
def test_ast_flatten(ast, tokens):
    assert list(cst_flatten(ast)) == tokens


def test_cst_roundtrip():
    tokenizer = Tokenizer.from_source("""\
hello world
<% code time %>

<%
much
more
code
%>

something else

<%= foo() %>

%% py
def add(x, y):
    return x + y
%% /py
%% some_block(x, y)
some block's content
%% py
print(3.1415)
%% /py
%% /some_block""")
    toks = [t for t in tokenizer._tokens]
    cst = cst_build(tokenizer)
    assert toks == [t for t in cst_flatten(cst)]


def test_cst_parser():
    tokenizer = Tokenizer.from_source("""\
hello world
<% code time %>

<%
much
more
code
%>

something else

<%= foo() %>

%% py
def add(x, y):
    return x + y
%% /py
%% some_block(x, y)
some block's content
%% py
print(3.1415)
%% /py
%% /some_block""")
    assert cst_build(tokenizer) == [
        [TokenType.TEXT, "hello world\n"],
        [TokenType.PY_BLOCK, "<% code time %>"],
        [TokenType.TEXT, "\n\n"],
        [TokenType.PY_BLOCK, "<%\nmuch\nmore\ncode\n%>"],
        [TokenType.TEXT, "\n\nsomething else\n\n"],
        [TokenType.PY_EXPR, "<%= foo() %>"],
        [TokenType.TEXT, "\n\n"],
        [TokenType.BLOCK, ["py"], "%% py\n",
         [TokenType.TEXT, "def add(x, y):\n    return x + y\n"], "%% /py\n"],
        [TokenType.TEXT, ""],
        [TokenType.BLOCK, ["some_block", "x, y"], "%% some_block(x, y)\n",
         [TokenType.TEXT, "some block's content\n"],
         [TokenType.BLOCK, ["py"], "%% py\n",
          [TokenType.TEXT, "print(3.1415)\n"], "%% /py\n"],
         [TokenType.TEXT, ""], "%% /some_block"],
        [TokenType.TEXT, ""],
    ]


def _eval_template(template: Template, render_ctx: dict):
    source_code = str(template._code)
    eval_env = {}
    # adds 'render_function' to context, otherwise unchanged
    exec(source_code, eval_env)
    res = eval("render_function(__gadfly_render_context__)", {
        **eval_env, "__gadfly_render_context__": render_ctx})
    return res


def _dump_template_to_file(template: Template, fpath) -> None:
    source_code = str(template._code)
    with open(fpath, "w") as fh:
        for line in source_code:
            fh.write(line)


@pytest.mark.parametrize("src, ctx, out", [
    ("hello, world!", {}, "hello, world!"),
    ("hello, <%= name %>!", {"name": "joe"}, "hello, joe!"),
    ("hello, <%= name %>!", {"name": "jane"}, "hello, jane!"),
    # code block alone does not effect the output
    ("<% 2 + 3 %>", {}, ""),
    # code block can influence render context
    ("<% x = 4 %>number <%= x %>!", {}, "number 4!"),
    # code block can read the existing render context and modify it
    ("<% x = x + 2 %>number <%= x %>!", {"x": 2}, "number 4!"),
])
def test_compiler_one_liners(src, ctx, out):
    cst = cst_build(Tokenizer.from_source(src))
    template = Template(cst, compilers={})
    # _dump_template_to_file(template, "/tmp/code.py")
    assert _eval_template(template, ctx) == out


@pytest.mark.parametrize("ctx, out", [
    ({"a": 1, "b": 5}, "Hello, world!\nSo, 1+5 -> 6")
])
def test_py_block_compiler(ctx, out):
    cst = cst_build(Tokenizer.from_source("""\
Hello, world!
%% py
def add(x, y):
    return x + y
%% /py
So, <%= a %>+<%= b %> -> <%= add(a, b) %>"""))
    template = Template(cst, compilers={"py": block_compile_py})
    assert _eval_template(template, ctx) == out
