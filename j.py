#!/usr/bin/env python3

import logging
import sys
import os
import tempfile
import time
import argparse
from datetime import datetime, timedelta
import subprocess

try:
    JRNL_DIR = os.environ["J_JOURNAL_DIR"]
except KeyError:
    print("Please set J_JOURNAL_DIR")
    sys.exit(1)

DEFAULT_DATE_FILTER = os.environ.get("J_JOURNAL_DEFAULT_TIME")

EDITOR = os.environ.get("EDITOR", "vi")
TIME_FORMAT = "%Y%m%d_%H%M%S"

RULE_SIZE = 78
DOUBLE_RULE = "=" * RULE_SIZE

WHEN_HELP = """Time formats for -w are of the form `start[:end]`, where start
and end are either an absolute time, or a time relative to now. Absolute times
are of the form `YYYY[-MM[-DD[ HH[:MM[:SS]]]]]`. Relative times are of the form
`nU` where `n` is a number and `U` is a unit drawn from `{M,h,d,w,m,y}` for
minutes, hours, days, weeks, months or years before now. If `end` is omitted,
then the end date is the distant future. If no -w is specified, then the
environment variable J_JOURNAL_DEFAULT_TIME is used, otherwise no date filter
is used.
"""


class FilterSettings:
    def __init__(self, tag_filters=None, textual_filters=None, time_filter=None):
        self.tag_filters = tag_filters
        self.textual_filters = textual_filters
        self.time_filter = time_filter


class TimeFilterException(Exception):
    pass


class TimeFilter:
    # The various absolute time formats j supports
    ABS_TIME_FMTS = [
        "%Y",
        "%Y-%m",
        "%Y-%m-%d",
        "%Y-%m-%d %H",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
    ]

    def __init__(self, start=None, stop=None):
        self.start = start
        self.stop = stop

    @classmethod
    def from_arg(cls, arg):
        # XXX allow only an end
        elems = arg.split(":")
        num_elems = len(elems)
        if not (1 <= num_elems <= 2):
            raise TimeFilterException()

        start = cls._parse_time_filter_elem(elems[0])
        if num_elems == 2:
            stop = cls._parse_time_filter_elem(elems[1])
        else:
            stop = None

        if stop and start > stop:
            raise TimeFilterException()
        return cls(start, stop)

    @staticmethod
    def _parse_time_filter_elem(elem):
        if len(elem) > 1 and elem[-1] in ("d", "w", "m", "y", "h", "M"):
            # relative to now
            try:
                num = int(elem[:-1])
            except ValueError:
                raise TimeFilterException()

            unit = elem[-1]

            if unit == "M":
                delta = timedelta(minutes=num)
            elif unit == "h":
                delta = timedelta(hours=num)
            elif unit == "d":
                delta = timedelta(days=num)
            elif unit == "w":
                delta = timedelta(days=num * 7)
            elif unit == "m":
                delta = timedelta(days=num * 31)  # roughly
            elif unit == "y":
                delta = timedelta(days=num * 365)  # roughly
            else:
                assert False  # unreachable

            return datetime.now() - delta
        else:
            for fmt in TimeFilter.ABS_TIME_FMTS:
                try:
                    return datetime.strptime(elem, fmt)
                except ValueError:
                    continue
            else:
                raise TimeFilterException()

    def matches(self, entry):
        if not self.start:
            assert not self.stop
            # filter matches anything
            return True

        if not self.stop:
            stop = datetime.now()
        else:
            stop = self.stop

        if self.start <= entry.time <= stop:
            return True
        else:
            return False


class ParseError(Exception):
    pass

class Entry:
    def __init__(self, path, meta_only=False):
        self.path = path
        self.title = None
        self.time = None
        self.body = None
        self.tags = set()
        self.parse(meta_only)

    def ident(self):
        return os.path.basename(self.path)

    def parse(self, meta_only=False):
        logging.debug("parsing '%s'" % self.path)
        # Get the time from the file path first
        tstr = os.path.basename(self.path).split("-")[0]
        self.time = datetime.strptime(tstr, TIME_FORMAT)

        with open(self.path) as fh:
            lines = iter(fh.readlines())

            try:
                # Required title line
                self.title = lines.__next__().strip()
                if self.title == "":
                    raise ParseError("no title")

                # Optional attribute line
                attr_line = lines.__next__().strip()
                if attr_line != "":
                    attrs = attr_line.split(" ")
                    # We only support tags here for now
                    for attr in attrs:
                        if not attr.startswith("@"):
                            raise ParseError("unknown attribue %s" % attr)
                    self.tags = set([x[1:] for x in attrs])

                    # Now expect a blank line
                    blank_line = lines.__next__().strip()
                    if blank_line != "":
                        raise ParseError("expected blank line after header")
                else:
                    pass  # blank attr line serves as the body separator

                if meta_only:
                    return

                self.body = "".join(lines)
            except StopIteration:
                raise ParseError("unexpected end of file")

    def __str__(self):
        time_str = str(self.time)
        pad = " " * (RULE_SIZE - len(time_str) - len(self.ident()))
        headers = [
            DOUBLE_RULE,
            "%s%s%s" % (time_str, pad, self.ident()),
            self.title.center(RULE_SIZE),
        ]
        if self.tags:
            atted_tags = ["@%s" % x for x in self.tags]
            headers.append(" ".join(atted_tags).center(RULE_SIZE))
        rec = "\n".join(headers)
        if self.body:
            rec += "\n\n%s" % self.body
        return rec

    def matches_tag(self, tag):
        return tag in self.tags

    def matches_term(self, term):
        with open(self.path) as fh:
            return term in fh.read()


class Journal:
    def __init__(self, directory):
        self.directory = directory

        if not os.path.exists(self.directory):
            logging.debug("creating '%s'" % self.directory)
            os.makedirs(self.directory)
        logging.debug("journal directory is '%s'" % self.directory)

    def new_entry(self):
        now = datetime.now()
        prefix = now.strftime("%s-" % TIME_FORMAT)
        fd, path = tempfile.mkstemp(dir=self.directory, prefix=prefix)
        os.close(fd)
        self._invoke_editor([path])

    def _collect_entries(self, filters, bodies=True):
        itr = os.scandir(self.directory)
        files = filter(lambda x: x.is_file(), itr)

        entries = []
        for fl in files:
                add = True
                entry = Entry(os.path.join(self.directory, fl.name),
                              meta_only=not bodies)

                # Only add if the time filter matches
                if filters.time_filter:
                    if not filters.time_filter.matches(entry):
                        continue

                # Only add if *all* tag filters match
                if filters.tag_filters:
                    matches = [entry.matches_tag(t) for t in filters.tag_filters]
                    if not all(matches):
                        continue

                # Only add if *all* textual filters match
                if filters.textual_filters:
                    matches = [entry.matches_term(t) for t in filters.textual_filters]
                    if not all(matches):
                        continue

                # Passed all filters
                entries.append(entry)
        return sorted(entries, key=lambda e: e.time)

    def show_entries(self, filters=None, bodies=True):
        if not filters:
            filters = FilterSettings()

        entries = self._collect_entries(bodies=bodies, filters=filters)
        for e in entries:
            print(str(e))

    def show_single_entry(self, ident, body=False):
        print(Entry(os.path.join(self.directory, ident), meta_only=not body))

    def edit_entry(self, ident):
        path = os.path.join(self.directory, ident)
        self._invoke_editor([path])

    def edit_tag(self, tag):
        filters = FilterSettings(tag_filters=[tag])
        entries = self._collect_entries(filters, bodies=False)
        self._invoke_editor([e.path for e in entries])

    def _invoke_editor(self, paths):
        while True:
            args = [EDITOR] + paths
            subprocess.check_call(args)

            problem_paths = []
            for path in paths:
                try:
                    Entry(path)  # just check it parses
                except ParseError as e:
                    problem_paths.append(path)
            if not problem_paths:
                break  # all is well
            print("Error! %d files failed to parse!" % len(problem_paths))
            print("Press enter to try again")
            paths = problem_paths
            input()


if __name__ == "__main__":
    if os.environ.get("J_JOURNAL_DEBUG"):
        logging.root.setLevel(logging.DEBUG)

    jrnl = Journal(JRNL_DIR)

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    new_parser = subparsers.add_parser('new', aliases=['n'])
    new_parser.set_defaults(mode='new')

    edit_parser = subparsers.add_parser('edit', aliases=['e'])
    edit_parser.set_defaults(mode='edit')
    edit_parser.add_argument("arg", nargs="*", help="entry id or tag to edit")

    show_parser = subparsers.add_parser('show', aliases=['s'], epilog=WHEN_HELP)
    show_parser.set_defaults(mode='show')
    show_parser.add_argument("arg", nargs="*", help="an id to show or @tags to filter by")
    show_parser.add_argument("--short", "-s", action="store_true", help="omit bodies")
    show_parser.add_argument("--term", "-t", nargs="*", default=None, help="Filter by search terms")
    show_parser.add_argument("--when", "-w", default=DEFAULT_DATE_FILTER, help="Filter by time")

    args = parser.parse_args()
    try:
        mode = args.mode
    except AttributeError:
        parser.print_help()
        sys.exit(1)

    if mode == "new":
        jrnl.new_entry()
    elif mode == "show":
        if len(args.arg) == 1 and not args.arg[0].startswith("@"):
            if args.term:
                print("--term (or -t) make no sense when displaying one entry")
                sys.exit(1)
            if args.when:
                print("--when (or -w) make no sense when displaying one entry")
                sys.exit(1)

            jrnl.show_single_entry(args.arg[0], body=not args.short)
        else:
            if not all([t.startswith("@") for t in args.arg]):
                print("all tags must begin with '@'")
                sys.exit(1)

            if args.when:
                try:
                    time_filter = TimeFilter.from_arg(args.when)
                except TimeFilterException:
                    print("invalid time filter")  # XXX improve message
                    sys.exit(1)
            else:
                time_filter = TimeFilter()

            tag_filters = [x[1:] for x in args.arg]
            textual_filters = args.term
            filters = FilterSettings(
                tag_filters=tag_filters,
                textual_filters=textual_filters,
                time_filter=time_filter
            )

            jrnl.show_entries(bodies=not args.short, filters=filters)
    elif mode == "edit":
        if len(args.arg) != 1:
            edit_parser.print_help()
            sys.exit(1)

        if args.arg[0].startswith("@"):
            jrnl.edit_tag(args.arg[0][1:])
        else:
            jrnl.edit_entry(args.arg[0])

    else:
        assert(False)  # unreachable
