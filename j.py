#!/usr/bin/env python3

import logging
import sys
import os
import datetime
import tempfile

# XXX change default
JRNL_DIR = os.environ.get("J_JOURNAL_PATH", os.path.abspath("j"))
EDITOR = os.environ.get("EDITOR", "vi")


class ParseError(Exception):
    pass

class Entry:
    def __init__(self, path):
        self.path = path
        self.title = None
        self.date = None
        self.body = None
        self.tags = set()
        self.parse()

    def parse(self):
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

                self.body = "".join(lines)
            except StopIteration:
                raise ParseError("unexpected end of file")


class Journal:
    def __init__(self, directory):
        self.directory = directory

        if not os.path.exists(self.directory):
            logging.debug("creating '%s'" % self.directory)
            os.makedirs(self.directory)
        logging.debug("journal directory is '%s'" % self.directory)

    def new_entry(self):
        now = datetime.datetime.now()
        prefix = now.strftime("%Y%m%d_%H%M%S_")
        fd, path = tempfile.mkstemp(dir=self.directory, prefix=prefix,
                                    suffix=".txt")
        os.close(fd)
        os.system("%s %s" % (EDITOR, path))
        try:
            Entry(path)  # just check it parses
        except ParseError as e:
            # XXX try again
            print("parsing failed: %s" % e)
            sys.exit(1)


if __name__ == "__main__":
    logging.root.setLevel(logging.DEBUG)
    jrnl = Journal(JRNL_DIR)
    jrnl.new_entry()
