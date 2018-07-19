import pytest
import support  # noqa: F401
from j import wrap
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
        assert wrap(input, i) == textwrap.wrap(input, i)


def test_preserve_list0001():
    for i in range(10, 100):
        got = wrap(LIST_INPUT1, 80)
        for j in 1, 2, 3:
            assert " - item%d" % j in got


def test_preserve_list0002():
    for i in range(10, 100):
        got = wrap(LIST_INPUT2, 80)
        for j in 1, 2, 3:
            assert " * item%d" % j in got
            assert "   - sub%d" % j in got


def test_paragraphs_preserved0001():
    n_paras = 20
    para = "here is a sentence. And here's another. " * 10
    input = ("\n".join([para, "\n"]) * n_paras).strip()

    for i in range(10, 100):
        got = wrap(input, i)
        assert got.count("") == n_paras - 1


def test_urls_preserved0001():
    silly_hostname = "a" * 500
    for i in range(10, 100):
        input = "http://{0}\nhttps://{0}".format(silly_hostname)
        assert "\n".join(wrap(input, i)) == input


def test_wrap_preserved0001():
    for i in range(10, 100):
        assert "\n".join(wrap(TRIPLE_INPUT1, i)) == TRIPLE_INPUT1
