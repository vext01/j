import support  # noqa: F401
import datetime
from datetime import timedelta
from support import jrnl  # noqa: F401
from support import now  # noqa: F401
from support import insert_entry, freeze_time
from j import TimeFilter, FilterSettings


def test_time_filter0001(jrnl):  # noqa: F811
    """Test ':' is unrestricted"""

    filters = FilterSettings(time_filter=TimeFilter.from_arg(":"))
    insert_entry(jrnl, title="hello1", time=datetime.datetime.min)
    insert_entry(jrnl, title="hello2", time=datetime.datetime.max)
    insert_entry(jrnl, title="hello3")
    ents = jrnl._collect_entries(filters=filters)

    assert len(ents) == 3


def test_time_filter0002(jrnl, now):  # noqa: F811
    """Test relative start time"""

    filters = FilterSettings(time_filter=TimeFilter.from_arg("1d"))
    insert_entry(jrnl, title="old", time=now - timedelta(days=3))
    path2 = insert_entry(jrnl, title="new")
    ents = jrnl._collect_entries(filters)

    assert len(ents) == 1
    assert ents[0].path == path2


def test_time_filter0003(jrnl, now):  # noqa: F811
    """Test relative end time"""

    filters = FilterSettings(time_filter=TimeFilter.from_arg(":1d"))
    path1 = insert_entry(jrnl, title="old", time=now - timedelta(days=3))
    insert_entry(jrnl, title="new")
    ents = jrnl._collect_entries(filters)

    assert len(ents) == 1
    assert ents[0].path == path1


def test_time_filter0004(jrnl, now):  # noqa: F811
    """Test relative start and end time"""

    filters = FilterSettings(time_filter=TimeFilter.from_arg("3d:1d"))
    insert_entry(jrnl, title="old", time=now - timedelta(days=5))
    path2 = insert_entry(jrnl, title="new", time=now - timedelta(days=2))
    insert_entry(jrnl, title="newer", time=now + timedelta(days=5))
    ents = jrnl._collect_entries(filters)

    assert len(ents) == 1
    assert ents[0].path == path2


def test_time_filter0005(jrnl, now):  # noqa: F811
    """Test absolute start time"""

    tstr = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    filters = FilterSettings(time_filter=TimeFilter.from_arg(tstr))
    insert_entry(jrnl, title="old", time=now - timedelta(days=3))
    path2 = insert_entry(jrnl, title="new")
    ents = jrnl._collect_entries(filters)

    assert len(ents) == 1
    assert ents[0].path == path2


def test_time_filter0006(jrnl, now):  # noqa: F811
    """Test absolute end time"""

    tstr = (now - timedelta(days=1)).strftime(":%Y-%m-%d")
    filters = FilterSettings(time_filter=TimeFilter.from_arg(tstr))
    path1 = insert_entry(jrnl, title="old", time=now - timedelta(days=3))
    insert_entry(jrnl, title="new")
    ents = jrnl._collect_entries(filters)

    assert len(ents) == 1
    assert ents[0].path == path1


def test_time_filter0008(jrnl, now):  # noqa: F811
    """Test absolute start and end time"""

    tstr1 = (now - timedelta(days=2)).strftime("%Y-%m-%d")
    tstr2 = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    tstr = "%s:%s" % (tstr1, tstr2)
    filters = FilterSettings(time_filter=TimeFilter.from_arg(tstr))
    insert_entry(jrnl, title="old", time=now - timedelta(days=5))
    path2 = insert_entry(jrnl, title="new", time=now - timedelta(days=2))
    insert_entry(jrnl, title="newer", time=now + timedelta(days=5))
    ents = jrnl._collect_entries(filters)

    assert len(ents) == 1
    assert ents[0].path == path2


def test_time_filter0009(jrnl, now):  # noqa: F811
    """Checks that a sticky entry unconditionally passes the time filter"""

    tstr = (now - timedelta(days=2)).strftime("%Y-%m-%d")
    filters = FilterSettings(time_filter=TimeFilter.from_arg(tstr))
    path = insert_entry(jrnl, title="old_sticky", time=now - timedelta(days=500 * 365), attrs="sticky")

    ents = jrnl._collect_entries(filters)
    assert len(ents) == 1
    assert ents[0].path == path


def test_parse_timespec0001(monkeypatch):
    """Test parsing years"""

    freeze_time(monkeypatch)
    tf = TimeFilter.from_arg("2y:1y")
    assert tf.start == TimeFilter.now() - timedelta(days=2 * 365)
    assert tf.stop == TimeFilter.now() - timedelta(days=365)


def test_parse_timespec0002(monkeypatch):
    """Test parsing months"""

    freeze_time(monkeypatch)
    tf = TimeFilter.from_arg("2m:1m")
    assert tf.start == TimeFilter.now() - timedelta(days=2 * 31)
    assert tf.stop == TimeFilter.now() - timedelta(days=31)


def test_parse_timespec0003(monkeypatch):
    """Test parsing days"""

    freeze_time(monkeypatch)
    tf = TimeFilter.from_arg("2d:1d")
    assert tf.start == TimeFilter.now() - timedelta(days=2)
    assert tf.stop == TimeFilter.now() - timedelta(days=1)


def test_parse_timespec0004(monkeypatch):
    """Test parsing hours"""

    freeze_time(monkeypatch)
    tf = TimeFilter.from_arg("2h:1h")
    assert tf.start == TimeFilter.now() - timedelta(hours=2)
    assert tf.stop == TimeFilter.now() - timedelta(hours=1)


def test_parse_timespec0005(monkeypatch):
    """Test parsing minutes"""

    freeze_time(monkeypatch)
    tf = TimeFilter.from_arg("2M:1M")
    assert tf.start == TimeFilter.now() - timedelta(minutes=2)
    assert tf.stop == TimeFilter.now() - timedelta(minutes=1)
