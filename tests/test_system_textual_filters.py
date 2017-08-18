from support import jrnl  # noqa: F401
from support import insert_entry, run_j
import datetime
import json


def test_textual_search0001(jrnl):  # noqa: F811
    """Check textual filter works and is not case sensitive by default"""

    dt = datetime.datetime(2017, 1, 1, 12, 00, 00)
    insert_entry(jrnl, "My Title", "@tag1 @tag2", "Body", time=dt,
                 fn_suffix="xxxxxxxx")
    out, err, rv = run_j(jrnl, ["s", "-j", "-t", "body"])
    assert rv == 0
    assert err.strip() == b""
    jsn = json.loads(out.strip())
    assert len(jsn["entries"]) == 1
    ent = jsn["entries"][0]

    assert ent["title"] == "My Title"
    assert ent["time"] == "2017-01-01 12:00:00"
    assert set(ent["tags"]) == set(["tag1", "tag2"])


def test_textual_search0002(jrnl):  # noqa: F811
    """Check case sensitive textual filter works"""

    dt = datetime.datetime(2017, 1, 1, 12, 00, 00)
    insert_entry(jrnl, "My Title", "@tag1 @tag2", "Body", time=dt,
                 fn_suffix="xxxxxxxx")
    out, err, rv = run_j(jrnl, ["s", "-j", "-c", "-t", "body"])
    assert rv == 0
    assert err.strip() == b""
    jsn = json.loads(out.strip())
    assert len(jsn["entries"]) == 0
