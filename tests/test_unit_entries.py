import tempfile
import pytest
import shutil
import support
import j


@pytest.fixture
def jrnl():
    """Makes a blank journal and tidies up when it falls out of scope"""

    path = tempfile.mkdtemp(dir=support.TEST_DIR)
    yield j.Journal(path)
    shutil.rmtree(path)


def test_collect_0001(jrnl):
    """Check an empty journal has 0 entries"""

    ents = jrnl._collect_entries()
    assert len(ents) == 0


def test_collect_0002(jrnl):
    """Check adding a title-only entry is OK"""

    jrnl._new_entry_create(title="hello")
    ents = jrnl._collect_entries()
    assert len(ents) == 1
    assert ents[0].title == "hello"


def test_empty_entry_0001(jrnl):
    """Check an entry with no title fails to parse gracefully"""

    jrnl._new_entry_create(title="")
    with pytest.raises(j.ParseError):
        jrnl._collect_entries()
