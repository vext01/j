#!/usr/bin/env python3

import logging
import sys
import os
import datetime
import tempfile
import time
import argparse

# XXX change default
JRNL_DIR = os.environ.get("J_JOURNAL_PATH", os.path.abspath("j"))
EDITOR = os.environ.get("EDITOR", "vi")
TIME_FORMAT = "%Y%m%d_%H%M%S"

RULE_SIZE = 78
DOUBLE_RULE = "=" * RULE_SIZE

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

    def show_entries(self, bodies=True, tag_filters=None, textual_filters=None):
        itr = os.scandir(self.directory)
        files = sorted(filter(lambda x: x.is_file(), itr), key=lambda x: x.name)

        entries = []
        for fl in files:
                entries.append(Entry(os.path.join(self.directory, fl.name),
                                     meta_only=not bodies))

        # Apply tag filters
        if tag_filters:
            filtered_entries = set([])
            for tag in tag_filters:
                filtered_entries |= set(
                    filter(lambda x: x.matches_tag(tag), entries)
                )
            entries = filtered_entries

        # Apply textual filters
        if textual_filters:
            filtered_entries = set([])
            for term in textual_filters:
                filtered_entries |= set(
                    filter(lambda x: x.matches_term(term), entries)
                )
            entries = filtered_entries

        for e in entries:
            print(str(e))

    def show_single_entry(self, ident, body=False):
        print(Entry(os.path.join(self.directory, ident), meta_only=not body))

    def edit_entry(self, ident):
        path = os.path.join(self.directory, ident)
        self._invoke_editor(path)

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

    new_parser = subparsers.add_parser('new')
    new_parser.set_defaults(mode='new')

    edit_parser = subparsers.add_parser('edit')
    edit_parser.set_defaults(mode='edit')
    edit_parser.add_argument("id", help="id of entry to edit")

    show_parser = subparsers.add_parser('show')
    show_parser.set_defaults(mode='show')
    show_parser.add_argument("arg", nargs="*", help="an id to show or @tags to filter by")
    show_parser.add_argument("--short", "-s", action="store_true", help="omit bodies")
    show_parser.add_argument("--term", "-t", nargs="*", help="Filter by search terms")

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
        if len(args.arg) == 1 and not args.arg[0].startswith("@"):
            # XXX -t makes no sense it this case
            jrnl.show_single_entry(args.arg[0], body=not args.short)
        else:
            # XXX check all tags start with @
            tag_filters = [x[1:] for x in args.arg]
            jrnl.show_entries(tag_filters=tag_filters,
                              textual_filters=args.term,
                              bodies=not args.short)
    elif mode == "edit":
        jrnl.edit_entry(args.id)
    else:
        assert(False)  # unreachable
