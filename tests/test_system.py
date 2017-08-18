from support import jrnl  # noqa: F401
from support import insert_entry, run_j
import datetime
import json


def test_no_journal_path_env0001():
    """Check that j warns if the journal path is not chosen"""

    out, err, rv = run_j(None, [])
    assert rv != 0
    assert err == b'Please set J_JOURNAL_DIR\n'


def test_no_args0001(jrnl):  # noqa: F811
    """Test an empty journal with no args works"""

    out, err, rv = run_j(jrnl, [])
    assert rv == 0
    assert out.strip() == err.strip() == b""


def test_show_entries0001(jrnl):  # noqa: F811
    """Check normal output works"""

    dt = datetime.datetime(2017, 1, 1, 12, 00, 00)
    insert_entry(jrnl, "My Title", "@tag1 @tag2", "Body", time=dt,
                 fn_suffix="xxxxxxxx")
    out, err, rv = run_j(jrnl, [])
    assert rv == 0
    assert err.strip() == b""
    lines = out.strip().splitlines()
    assert len(lines) == 6

    assert lines[0] == \
        b'=========================================================' \
        b'====================='

    assert lines[1] == \
        b'2017-01-01 12:00:00                                   ' \
        b'20170101_120000-xxxxxxxx'

    assert lines[2].strip() == b'My Title'
    assert lines[3].strip() == b'@tag1 @tag2' or \
        lines[3].strip() == b'@tag2 @tag1'
    assert lines[4] == b''
    assert lines[5] == b'Body'


def test_show_entries0002(jrnl):  # noqa: F811
    """Check normal output works"""

    dt = datetime.datetime(2017, 1, 1, 12, 00, 00)
    insert_entry(jrnl, "My Title", "@tag1 @tag2", "Body", time=dt,
                 fn_suffix="xxxxxxxx")
    out, err, rv = run_j(jrnl, ["s", "-j"])
    assert rv == 0
    assert err.strip() == b""
    jsn = json.loads(out.strip())
    assert len(jsn["entries"]) == 1
    ent = jsn["entries"][0]

    assert ent["title"] == "My Title"
    assert ent["time"] == "2017-01-01 12:00:00"
    assert set(ent["tags"]) == set(["tag1", "tag2"])
