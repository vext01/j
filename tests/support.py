# Miscellaneous support for testing
import os
import sys
import tempfile
import pytest
import shutil
import datetime

TEST_DIR = os.path.dirname(__file__)
PARENT_DIR = os.path.abspath(os.path.join(TEST_DIR, ".."))
sys.path.insert(0, PARENT_DIR)

import j  # noqa: E402


@pytest.fixture
def jrnl():
    """Makes a blank journal and tidies up when it falls out of scope"""

    path = tempfile.mkdtemp(dir=TEST_DIR)
    yield j.Journal(path)
    shutil.rmtree(path)


def insert_entry(jrnl, title, attrs=None, body=None, time=None,
                 fn_suffix=None):
    """
    Helper to insert entries (directly) into a journal dir from the test suite.
    """

    if not time:
        time = datetime.datetime.now()
    else:
        assert type(time) is datetime.datetime, \
            "time must be a datetime object"

    prefix = time.strftime("%s-" % j.TIME_FORMAT)
    if not fn_suffix:
        fd, path = tempfile.mkstemp(prefix=prefix, dir=jrnl.directory)
    else:
        path = "%s%s" % (prefix, fn_suffix)
        fd = os.open(path, os.O_CREAT)

    # Populate the file
    os.write(fd, (title + "\n").encode(sys.getdefaultencoding()))
    if attrs:
        os.write(fd, (attrs + "\n").encode(sys.getdefaultencoding()))
    if body:
        os.write(fd, ("\n" + body).encode(sys.getdefaultencoding()))

    os.close(fd)
    return path


@pytest.fixture
def now():
    return datetime.datetime.now()


def freeze_time(monkeypatch):
    now = datetime.datetime.now()

    def fake_datetime_now():
        return now
    monkeypatch.setattr(j.TimeFilter, "now",  fake_datetime_now)
