import pytest
import support  # noqa: F401
from j import format_body
import textwrap

LIST_INPUT1 = """this is a test
line2
line3

 - item1
 - item2
 - item3

after1
after2, and the end"""


LIST_INPUT2 = """this is a test
line2
line3

 * item1
   - sub1

Paragraph in the middle.

 * item2
   - sub2
   - sub3
 * item3

after1
after2, and the end"""

TRIPLE_INPUT1 = """start

```
123
456
789
```

end"""


def test_basic_wrap0001():
    input = "This is a test. " * 100
    for i in range(10, 100):
        assert format_body(input, i) == textwrap.wrap(input, i)


def test_preserve_list0001():
    for i in range(10, 100):
        got = format_body(LIST_INPUT1, 80)
        for j in 1, 2, 3:
            assert " - item%d" % j in got


def test_preserve_list0002():
    for i in range(10, 100):
        got = format_body(LIST_INPUT2, 80)
        for j in 1, 2, 3:
            assert " * item%d" % j in got
            assert "   - sub%d" % j in got


def test_paragraphs_preserved0001():
    n_paras = 20
    para = "here is a sentence. And here's another. " * 10
    input = ("\n".join([para, "\n"]) * n_paras).strip()

    for i in range(10, 100):
        got = format_body(input, i)
        assert got.count("") == n_paras - 1


def test_urls_preserved0001():
    silly_hostname = "a" * 500
    for i in range(10, 100):
        input = "http://{0}\nhttps://{0}".format(silly_hostname)
        assert "\n".join(format_body(input, i)) == input


def test_triple_backticks0001():
    expect = "start\n\n/\n| 123\n| 456\n| 789\n\\\n\nend"
    for i in range(10, 100):
        assert "\n".join(format_body(TRIPLE_INPUT1, i)) == expect


def test_no_trailing_newline0001():
    input = " - list item"
    for i in range(10, 100):
        assert "\n".join(format_body(input, i)) == input


def test_no_trailing_newline0002():
    input = "```\n123\n```"
    expect = "/\n| 123\n\\"
    for i in range(10, 100):
        assert "\n".join(format_body(input, i)) == expect
