import pytest
import support  # noqa: F401
from support import jrnl  # noqa: F401
from support import insert_entry
import j
from j import Entry


def test_collect_0001(jrnl):  # noqa: F811
    """Check an empty journal has 0 entries"""

    ents = jrnl._collect_entries()
    assert len(ents) == 0


def test_collect_0002(jrnl):  # noqa: F811
    """Check adding a title-only entry is OK"""

    insert_entry(jrnl, title="hello")
    ents = jrnl._collect_entries()
    assert len(ents) == 1


def test_collect_0003(jrnl):  # noqa: F811
    """Check adding many entries works"""

    for i in range(128):
        insert_entry(jrnl, title="hello%s" % i)
        ents = jrnl._collect_entries()

    assert len(ents) == 128


def test_parse_entry_0001(jrnl):  # noqa: F811
    """Check a typical entry parses"""

    path = insert_entry(jrnl, title="title", attrs="@tag", body="body\nbody")
    ent = Entry(path)

    assert ent.title == "title"
    assert ent.tags == {"tag"}
    assert ent.body == "body\nbody"


def test_parse_entry_0002(jrnl):  # noqa: F811
    """Check an entry with no title fails to parse gracefully"""

    path = insert_entry(jrnl, title="")
    with pytest.raises(j.ParseError) as e:
        Entry(path)
    assert "whitespace title" in str(e)


def test_parse_entry_0003(jrnl):  # noqa: F811
    """Check an entry with no title fails to parse gracefully"""

    path = insert_entry(jrnl, title="")
    with pytest.raises(j.ParseError) as e:
        Entry(path)
    assert "whitespace title" in str(e)


def test_parse_entry_0004(jrnl):  # noqa: F811
    """Check a title only entry parses"""

    path = insert_entry(jrnl, title="title")
    ent = Entry(path)

    assert ent.title == "title"
    assert ent.tags == set()
    assert ent.body is None


def test_parse_entry_0005(jrnl):  # noqa: F811
    """Check an entry with no attributes parses"""

    path = insert_entry(jrnl, title="title", body="123\n456")
    ent = Entry(path)

    assert ent.title == "title"
    assert ent.tags == set()
    assert ent.body == "123\n456"


def test_parse_entry_0006(jrnl):  # noqa: F811
    """Check an entry with a single invalid attr fails to parse"""

    path = insert_entry(jrnl, title="title", attrs="zzz")
    with pytest.raises(j.ParseError) as e:
        Entry(path)
    assert "unknown attribute" in str(e)


def test_parse_entry_0007(jrnl):  # noqa: F811
    """Check an entry with invalid and valid attrs fails to parse"""

    path = insert_entry(jrnl, title="title", attrs="@ok @also-ok bad")
    with pytest.raises(j.ParseError) as e:
        Entry(path)
    assert "unknown attribute" in str(e)


def test_parse_entry_0008(jrnl):  # noqa: F811
    """Check an entry with no body parses OK"""

    path = insert_entry(jrnl, title="title", attrs="@tag")
    ent = Entry(path)
    assert ent.title == "title"
    assert ent.tags == {"tag"}
    assert ent.body is None


def test_parse_entry_0009(jrnl):  # noqa: F811
    """Check an entry with unicode doesn't explode"""

    path = insert_entry(jrnl, title="τοῦ", attrs="@Конф", body="สิบสอง")
    ent = Entry(path)
    assert ent.title == "τοῦ"
    assert ent.tags == {"Конф"}
    assert ent.body == "สิบสอง"


def test_parse_entry_0010(jrnl):  # noqa: F811
    """Check an entry with multiple tags works"""

    path = insert_entry(jrnl, title="title", attrs="@t1 @t2 @t3")
    ent = Entry(path)
    assert ent.title == "title"
    assert ent.tags == {"t1", "t2", "t3"}
    assert ent.body is None
