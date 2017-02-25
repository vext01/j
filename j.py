#!/usr/bin/env python3

import logging
import sys
import os
import datetime
import tempfile
import time

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
        os.system("%s %s" % (EDITOR, path))
        try:
            Entry(path)  # just check it parses
        except ParseError as e:
            # XXX try again
            print("parsing failed: %s" % e)
            sys.exit(1)

    def show(self, bodies=False):
        itr = os.scandir(self.directory)
        files = sorted(filter(lambda x: x.is_file(), itr), key=lambda x: x.name)

        if len(files):
            for fl in files:
                print("%s" % Entry(
                    os.path.join(self.directory, fl.name), meta_only=not bodies))

if __name__ == "__main__":
    logging.root.setLevel(logging.DEBUG)
    jrnl = Journal(JRNL_DIR)

    if len(sys.argv) == 1:  # no args
        jrnl.new_entry()
    else:
        if sys.argv[1] == "ls":
            jrnl.show()
        elif sys.argv[1] == "show":
            jrnl.show(bodies=True)

