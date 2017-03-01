#!/usr/bin/env python3

import logging
import sys
import os
import datetime
import tempfile
import time
import argparse

try:
    JRNL_DIR = os.environ["J_JOURNAL_DIR"]
except KeyError:
    print("Please set J_JOURNAL_DIR")
    sys.exit(1)

EDITOR = os.environ.get("EDITOR", "vi")
TIME_FORMAT = "%Y%m%d_%H%M%S"

RULE_SIZE = 78
DOUBLE_RULE = "=" * RULE_SIZE


class FilterSettings:
    def __init__(self, tag_filters=None, textual_filters=None):
        self.tag_filters = tag_filters
        self.textual_filters = textual_filters


class ParseError(Exception):
    pass

class Entry:
    def __init__(self, path, meta_only=False):
        self.path = path
        self.title = None
        self.date = None
        self.body = None
        self.tags = set()
        self.parse(meta_only)

    def ident(self):
        return os.path.basename(self.path)

    def parse(self, meta_only=False):
        # Get the time from the file path first
        tstr = os.path.basename(self.path).split("-")[0]
        self.date = datetime.datetime.strptime(tstr, TIME_FORMAT)

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
        date_str = str(self.date)
        pad = " " * (RULE_SIZE - len(date_str) - len(self.ident()))
        headers = [
            DOUBLE_RULE,
            "%s%s%s" % (date_str, pad, self.ident()),
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
        now = datetime.datetime.now()
        prefix = now.strftime("%s-" % TIME_FORMAT)
        fd, path = tempfile.mkstemp(dir=self.directory, prefix=prefix)
        os.close(fd)
        self._invoke_editor(path)

    def _collect_entries(self, filters, bodies=True):
        itr = os.scandir(self.directory)
        files = filter(lambda x: x.is_file(), itr)

        entries = []
        for fl in files:
                add = True
                entry = Entry(os.path.join(self.directory, fl.name),
                              meta_only=not bodies)

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
        return sorted(entries, key=lambda e: e.date)

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
        self._invoke_editor(path)

    def edit_tag(self, tag):
        # XXX if there are lots of matches, how does the user exit?
        # XXX edit tag with timeframe?
        filters = FilterSettings(tag_filters=[tag])
        entries = self._collect_entries(filters, bodies=False)
        for entry in entries:
            self._invoke_editor(entry.path)

    def _invoke_editor(self, path):
        os.system("%s %s" % (EDITOR, path))
        try:
            Entry(path)  # just check it parses
        except ParseError as e:
            # XXX try again
            # Offer to delete if not and this is a new entry?
            print("parsing failed: %s" % e)
            sys.exit(1)

if __name__ == "__main__":
    logging.root.setLevel(logging.DEBUG)
    jrnl = Journal(JRNL_DIR)

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    new_parser = subparsers.add_parser('new', aliases=['n'])
    new_parser.set_defaults(mode='new')

    edit_parser = subparsers.add_parser('edit', aliases=['e'])
    edit_parser.set_defaults(mode='edit')
    edit_parser.add_argument("arg", nargs="*", help="entry id or tag to edit")

    show_parser = subparsers.add_parser('show', aliases=['s'])
    show_parser.set_defaults(mode='show')
    show_parser.add_argument("arg", nargs="*", help="an id to show or @tags to filter by")
    show_parser.add_argument("--short", "-s", action="store_true", help="omit bodies")
    show_parser.add_argument("--term", "-t", nargs="*", default=None, help="Filter by search terms")

    args = parser.parse_args()
    try:
        mode = args.mode
    except AttributeError:
        mode = "show"
        parser.print_help()
        sys.exit(1)

    if mode == "new":
        jrnl.new_entry()
    elif mode == "show":
        filters = FilterSettings()
        if len(args.arg) == 1 and not args.arg[0].startswith("@"):
            # XXX -t makes no sense it this case
            jrnl.show_single_entry(args.arg[0], body=not args.short)
        else:
            # XXX check all tags start with @
            filters.tag_filters = [x[1:] for x in args.arg]
            filters.textual_filters = args.term
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
