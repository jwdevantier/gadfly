from gadfly.templating import tokenize, TTemplate
import pytest


def test_something_cool():
    x = tokenize("""
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
    assert x == [
        "\nhello world\n",
        "<% code time %>",
        "\n\n",
        "<%\nmuch\nmore\ncode\n%>",
        "\n\nsomething else\n\n",
        "<%= foo() %>",
        "\n\n",
        "%% py",
        "\n",
        "%% /py",
        "\n"
    ]


def _eval_template(template: TTemplate, render_ctx: dict):
    source_code = str(template._code)
    eval_env = {}
    # adds 'render_function' to context, otherwise unchanged
    exec(source_code, eval_env)
    res = eval("render_function(__gadfly_render_context__)", {
        **eval_env, "__gadfly_render_context__": render_ctx})
    return res


def _dump_template_to_file(template: TTemplate, fpath) -> None:
    source_code = str(template._code)
    with open(fpath, "w") as fh:
        for line in source_code:
            fh.write(line)


@pytest.mark.parametrize("expr, context, result", [
    ("5 + 5", {}, "10"),
    (""""hello" + "world" + '!'""", {}, "helloworld!"),
    # test rendering using provided context
    ("pi", {"pi": 3.1415}, "3.1415"),
])
def test_code_expr(expr, context, result):
    template = TTemplate(f"""<%= {expr} %>""")
    assert _eval_template(template, context) == result


def test_code_exprs_and_code_blocks__no_context():
    template = TTemplate("""\
hello, I am <%= 2 + 3 %> years old!
<%
def add2(x, y):
    return x + y
%>
So, 3 + 2 is <%= add2(3, 2) %>!""")
    assert _eval_template(template, {}) == """\
hello, I am 5 years old!

So, 3 + 2 is 5!"""