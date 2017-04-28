import pytest
import support  # noqa: F401
from support import jrnl  # noqa: F401
from support import insert_entry


@pytest.fixture
def filters():
    from j import FilterSettings
    return FilterSettings()


def test_textual_filter_0001(jrnl, filters):  # noqa: F811
    """Check search of entry body works"""

    insert_entry(jrnl, title="About the BBQ", body="Toxic BBQ")
    insert_entry(jrnl, title="Crew", body="Kryten, Lister, Cat, Rimmer")

    filters.textual_filters = ["Toxic"]
    ents = jrnl._collect_entries(filters)
    assert len(ents) == 1
    assert ents[0].title == "About the BBQ"


def test_textual_filter_0002(jrnl, filters):  # noqa: F811
    """Check search of entry title works"""

    insert_entry(jrnl, title="About the BBQ", body="Toxic BBQ")
    insert_entry(jrnl, title="Crew", body="Kryten, Lister, Cat, Rimmer")

    filters.textual_filters = ["Crew"]
    ents = jrnl._collect_entries(filters)
    assert len(ents) == 1
    assert ents[0].title == "Crew"


def test_textual_filter_0003(jrnl, filters):  # noqa: F811
    """Check multiple hits"""

    for i in range(20):
        insert_entry(jrnl, title="title%s" % i, body="test")

    filters.textual_filters = ["5"]
    ents = jrnl._collect_entries(filters)
    assert len(ents) == 2
    assert ents[0].title == "title5"
    assert ents[1].title == "title15"


def test_textual_filter_0004(jrnl, filters):  # noqa: F811
    """Check search is case sensitive"""

    insert_entry(jrnl, title="About the BBQ", body="Toxic BBQ")
    filters.textual_filters = ["toxic"]
    ents = jrnl._collect_entries(filters)
    assert len(ents) == 0
