#!/usr/bin/env python3

import logging
import sys
import os
import tempfile
import argparse
import io
import json
import textwrap
from datetime import datetime, timedelta
import subprocess
import shutil


TIME_FORMAT = "%Y%m%d_%H%M%S"

DEFAULT_EDITOR = "vi"
DEFAULT_PAGER = "less -R"
DEFAULT_WRAP_COL = 78

TMP = tempfile.gettempdir()

HELP_EPILOG = """ENTRY FORMAT
------------

Each journal entry is a plain text file with a special header.

The first line of an entry is the title of the entry.

An optional second line can be used to specify a list of space-separated
"attributes" of the entry. Valid attributes are:

 * 'immortal' -- The entry always passes the time filter.
 * 'nowrap' -- Do not wrap the paragraphs in this entry.
 * Any string starting with '@' -- Adds a "tag" to the post. Multiple tags
   may be specified.

After the title line and the optional attribute line, a blank line must appear,
then the remainder of the file is the "body" of the entry.

The body is then interpreted as a markdown-like language:

 * Paragraphs are wrapped. The wrapping extent is configured with the
   J_JOURNAL_WRAP_COL environment detailed below.
 * Markdown-style lists are supported.
 * Lines that begin with `http://` or `https://` will not be wrapped.
 * Triple backtick lines toggle wrapping on and off (for code samples).
 * Markdown-style hash headers are supported, but underline ones are not.

TIME FORMATS
------------

Time formats are of the form:

    [start][:[end]]

Where start and end are either an absolute time, or a relative time prior to
the instant of invocation.

Absolute times are of the form:

    YYYY[-MM[-DD[HH[:MM[:SS]]]]]

Relative times are of the form `nU` where `n` is a number and `U` is a unit
drawn from `{M,h,d,w,m,y}` for minutes, hours, days, weeks, months or years
before now. If `start` is omitted, then the start time is the distant past. If
`end` is omitted, then the end time is the distant future.

CONFIGURATION
-------------

All configuration is done via environment variables. The following variables
are available:

    J_JOURNAL_DEBUG
        Set to see some debug output.

    J_JOURNAL_COLOURS
        A string encoding the colour scheme for journal entries. The string is
        a comma separated list of `key=value` pairs.

        Valid keys are:
            meta:   the colour for entry meta-data
            title:  the colour for entry titles
            attrs:  the colour for the entry attribute lines
            rule:   the colour of the separating rule between entries
            body:   the colour of entry bodies

        Valid values are:
            red, green, yellow, blue, magenta, cyan, white, bright-red,
            bright-green, bright-yellow, bright-blue, bright-magenta,
            bright-cyan, bright-white.

        If unset, colours are off.

    J_JOURNAL_DIR
        The directory in which to store journal entries. This is required.

    J_JOURNAL_TIME
        The default time filter. See TIME FORMATS for syntax.

    J_JOURNAL_WRAP_COL
        Change the column at which entries are wrapped. If negative, turns off
        wrapping for the entry body and the absolute value is used as the width
        of the entry headers and separating rules. The default value is %s. See
        also the 'nowrap' entry attribute.

    EDITOR
        The editor command to use to edit journal entries. It must support
        multiple file names on the command line. If unset, defaults to '%s'.

    PAGER
        The pager command used to scroll entries. If unset, defaults to
        '%s'.
""" % (DEFAULT_WRAP_COL, DEFAULT_EDITOR, DEFAULT_PAGER)


def print_err(msg, newline=True):
    sys.stderr.write(msg)
    if newline:
        sys.stderr.write("\n")
    sys.stderr.flush()


class Colours(dict):
    # ANSI colour sequences for:
    KEYS = [
        "meta",         # entry meta-data, e.g. ID, date, ...
        "title",        # entry title
        "attrs",        # attributes line
        "rule",         # rule between entries
        "body",         # entry body text
    ]

    ANSI_COLOURS = {
        "red":              "\033[0;31m",
        "green":            "\033[0;32m",
        "yellow":           "\033[0;33m",
        "blue":             "\033[0;34m",
        "magenta":          "\033[0;35m",
        "cyan":             "\033[0;36m",
        "white":            "\033[0;37m",
        "bright-red":       "\033[1;31m",
        "bright-green":    "\033[1;32m",
        "bright-yellow":   "\033[1;33m",
        "bright-blue":     "\033[1;34m",
        "bright-magenta":  "\033[1;35m",
        "bright-cyan":     "\033[1;36m",
        "bright-white":    "\033[1;37m",
    }

    ANSI_RESET = "\033[0;0m"

    def __init__(self):
        # These get set to ANSI escape chars if the user specifies a colour
        for k in Colours.KEYS:
            self[k] = ""  # defaults to no colour
        self.reset_seq = ""

    @classmethod
    def from_str(cls, spec_str):
        inst = cls()

        pairs = spec_str.split(",")

        # If at least one colour is set, then start using ANSI_RESET
        if pairs:
            inst.reset_seq = Colours.ANSI_RESET

        for pair in pairs:
            try:
                k, v = pair.split("=")
            except ValueError:
                print("malformed colour setting: '%s'" % pair)
                sys.exit()

            if k not in inst.keys():
                print("unknown colour key: '%s'" % k)
                sys.exit()

            try:
                esc_seq = Colours.ANSI_COLOURS[v]
            except KeyError:
                print("Unknown colour: '%s'" % v)
                sys.exit()

            inst[k] = esc_seq
        return inst

    def reset(self):
        return self.reset_seq


class FilterSettings:
    def __init__(self, tag_filters=None, textual_filters=None,
                 time_filter=None, id_filters=None, case_sensitive=False):
        self.tag_filters = tag_filters
        self.textual_filters = textual_filters
        self.case_sensitive = case_sensitive
        self.time_filter = time_filter
        self.id_filters = id_filters


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

    def __init__(self, start=datetime.min, stop=datetime.max):
        self.start = start
        self.stop = stop

    @staticmethod
    def now():
        # separate for testing with monkeypatch
        return datetime.now()

    @classmethod
    def from_arg(cls, arg):
        elems = arg.split(":")
        num_elems = len(elems)
        if not (1 <= num_elems <= 2):
            raise TimeFilterException("wrong number of time elements")

        start = cls._parse_time_filter_elem(elems[0], "start")
        stop = datetime.max  # distant future
        if num_elems == 2:
            stop = cls._parse_time_filter_elem(elems[1], "stop")

        if start > stop:
            raise TimeFilterException("start time is later than stop time")
        return cls(start, stop)

    @staticmethod
    def _parse_time_filter_elem(elem, which):
        assert which in ["start", "stop"]

        if elem == "":
            # No constraint
            if which == "start":
                return datetime.min  # the distant past
            else:
                return datetime.max  # the distant future
        elif len(elem) > 1 and elem[-1] in ("d", "w", "m", "y", "h", "M"):
            # relative to now
            try:
                num = int(elem[:-1])
            except ValueError:
                raise TimeFilterException("bogus time spec element")

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

            return TimeFilter.now() - delta
        else:
            for fmt in TimeFilter.ABS_TIME_FMTS:
                try:
                    return datetime.strptime(elem, fmt)
                except ValueError:
                    continue
            else:
                raise TimeFilterException("bogus time spec element")

    def matches(self, entry):
        if not self.start:
            assert not self.stop
            # filter matches anything
            return True

        if not self.stop:
            stop = TimeFilter.now()
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
        self.immortal = False
        self.wrap = True
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

            # Required title line
            try:
                self.title = lines.__next__().strip()
                if self.title.strip() == "":
                    raise ParseError("whitespace title")
            except StopIteration:
                raise ParseError("unexpected end of file")

            # Attribute line or EOF
            try:
                attr_line = lines.__next__().strip()
            except StopIteration:
                return

            if attr_line != "":
                attrs = attr_line.split(" ")
                for attr in attrs:
                    if attr.startswith("@"):
                        self.tags.add(attr[1:])
                    elif attr == "immortal":
                        self.immortal = True
                    elif attr == "nowrap":
                        self.wrap = False
                    else:
                        raise ParseError("unknown attribute %s" % attr)

                # Now expect a blank line or EOF
                try:
                    blank_line = lines.__next__().strip()
                    if blank_line != "":
                        raise ParseError("expected blank line after header")
                except StopIteration:
                    return
            else:
                pass  # blank attr line serves as the body separator

            if meta_only:
                return

            self.body = "".join(lines)

    def format(self, wrap_col, colours=None):
        if not colours:
            colours = Colours()  # default colours (i.e. none)

        header_wrap = abs(wrap_col)
        time_str = str(self.time)
        pad = " " * (header_wrap - len(time_str) - len(self.ident()))
        rule = header_wrap * "="
        headers = [
            "%s%s%s" % (colours["rule"], rule, colours.reset()),
            "%s%s%s%s%s" % (colours["meta"], time_str, pad, self.ident(),
                            colours.reset()),
            "%s%s%s" % (colours["title"], self.title.center(header_wrap),
                        colours.reset()),
        ]
        if self.tags:
            atted_tags = ["@%s" % x for x in self.tags]
            attr_line = " ".join(atted_tags).center(header_wrap)
            headers.append("%s%s%s" % (colours["attrs"], attr_line,
                                       colours.reset()))
        rec = "\n".join(headers)
        if self.body:
            # ANSI colours reset at EOL, so we have to mark up each line
            rec += "\n\n"
            if not self.wrap:
                wrap_col = -1

            for line in format_body(self.body, wrap_col):
                rec += ("%s%s%s\n" % (colours["body"], line, colours.reset()))
        return rec

    def as_dict(self):
        """Return the entries attributes as a dict (used for JSON encoding)"""

        return {
            "path": self.path,
            "title": self.title,
            "time": str(self.time),
            "body": self.body,
            "tags": list(self.tags),
        }

    def matches_tag(self, tag):
        return tag in self.tags

    def matches_text(self, text, case_sensitive=False):
        with open(self.path) as fh:
            contents = fh.read()
            if not case_sensitive:
                contents = contents.lower()
                text = text.lower()
            return text in contents

    def matches_ids(self, ids):
        return os.path.basename(self.path) in ids


class Journal:
    def __init__(self, directory, colours=None, editor=DEFAULT_EDITOR,
                 pager=DEFAULT_PAGER, wrap_col=DEFAULT_WRAP_COL):
        """Makes a journal instance.

        Args:
          directory (str): path to journal storage directory
          colours (Colours): A Colours instance or None.
          pager (str): Pager command and args or None.
        """

        self.directory = directory
        self.colours = colours
        self.editor = editor
        self.pager = pager
        if not colours:
            colours = Colours()
        self.colours = colours
        self.wrap_col = wrap_col

        if not os.path.exists(self.directory):
            logging.debug("creating '%s'" % self.directory)
            os.makedirs(self.directory)
        logging.debug("journal directory is '%s'" % self.directory)

    def _new_entry_create(self, **contents):
        """Create a new file for a new entry."""

        now = TimeFilter.now()
        prefix = now.strftime("%s-" % TIME_FORMAT)
        fd, path = tempfile.mkstemp(prefix=prefix)
        os.close(fd)
        return path

    def _move_entry_in(self, path, existing):
        basename = os.path.basename(path)
        new_path = os.path.join(self.directory, basename)
        if not existing:
            assert not os.path.exists(new_path)
        shutil.move(path, new_path)
        return new_path

    def new_entry(self):
        path = self._new_entry_create()
        self._invoke_editor([path], existing=False)

    def _collect_entries(self, filters=None, bodies=True):
        if filters is None:
            filters = FilterSettings()

        itr = os.scandir(self.directory)
        files = filter(lambda x: x.is_file(), itr)

        entries = []
        for fl in files:
                fname = fl.name

                # Skip dotfiles (that may be to do with file synchronisers)
                if fname.startswith("."):
                    continue

                entry = Entry(os.path.join(self.directory, fname),
                              meta_only=not bodies)

                # Only add if the time filter matches
                # XXX invert the relationship between the filter an the entry
                # like the other filters XXX.
                if not entry.immortal and filters.time_filter:
                    if not filters.time_filter.matches(entry):
                        continue

                # Only add if *all* tag filters match
                if filters.tag_filters:
                    matches = [entry.matches_tag(t) for t in
                               filters.tag_filters]
                    if not all(matches):
                        continue

                # Only add if *all* textual filters match
                if filters.textual_filters:
                    matches = [
                        entry.matches_text(
                            t, case_sensitive=filters.case_sensitive)
                        for t in filters.textual_filters]
                    if not all(matches):
                        continue

                # Only add if the id matches one of the id filters
                if filters.id_filters:
                    if not entry.matches_ids(filters.id_filters):
                        continue

                # Passed all filters
                entries.append(entry)
        return sorted(entries, key=lambda e: e.time, reverse=True)

    def show_entries(self, filters=None, bodies=True, output_json=False):
        if not filters:
            filters = FilterSettings()

        entries = self._collect_entries(bodies=bodies, filters=filters)

        of = io.StringIO()
        if not output_json:
            for e in entries:
                of.write(e.format(self.wrap_col, self.colours) + "\n")
        else:
            dcts = [e.as_dict() for e in entries]
            of.write(json.dumps({"entries": dcts}, indent=2))

        if entries and self.pager and sys.stdout.isatty():
            p = subprocess.Popen(self.pager, shell=True, stdin=subprocess.PIPE)
            sout, serr = p.communicate(
                of.getvalue().encode(sys.getdefaultencoding()))
            if p.returncode != 0:
                print("failed to run '%s'" % self.pager)
                sys.exit(1)
        else:
            print(of.getvalue())

    def _edit_existing_entries(self, entries):
        """
        Edit a list of existing entries using an intermediate location in
        the temporary directory.

        Args:
          entries (list of str): list of existing entries to edit
        """

        if len(entries) == 0:
            return

        tmp_paths = []
        for ent in entries:
            path = ent.path
            basename = os.path.basename(path)
            tmp_path = os.path.join(TMP, basename)
            shutil.copyfile(path, tmp_path)
            tmp_paths.append(tmp_path)
        self._invoke_editor(tmp_paths, existing=True)

    def edit_entry(self, ident):
        if ident.startswith("^"):
            # Relative addressing.
            filters = FilterSettings()
            entries = self._collect_entries(bodies=False, filters=filters)

            try:
                idx = int(ident[1:])
            except ValueError:
                idx = -1

            if idx < 0 or idx >= len(entries):
                print("Invalid index")
                sys.exit(1)

            self._edit_existing_entries([entries[idx]])
        else:
            path = os.path.join(self.directory, ident)
            entry = Entry(path)
            self._edit_existing_entries([entry])

    def edit_tag(self, tag):
        filters = FilterSettings(tag_filters=[tag])
        entries = self._collect_entries(filters, bodies=False)
        self._edit_existing_entries(entries)

    def _invoke_editor(self, paths, existing=False):
        while True:
            args = [self.editor] + paths
            subprocess.check_call(args)

            problem_paths = {}
            for path in paths:
                try:
                    Entry(path)  # just check it parses
                except ParseError as e:
                    problem_paths[path] = str(e)
                    print("[!] %s" % path)
                else:
                    new_path = self._move_entry_in(path, existing)
                    if existing:
                        print("[E] %s" % new_path)
                    else:
                        print("[N] %s" % new_path)
            if not problem_paths:
                break  # all is well
            print("\nError! %d files failed to parse:" % len(problem_paths))
            for path, reason in problem_paths.items():
                print("  %s: %s" % (path, reason))

            print("\nPress enter to try again")
            paths = list(problem_paths.keys())
            try:
                input()
            except KeyboardInterrupt:
                print("\nTemproary entries retained:")
                for i in paths:
                    print(" + %s" % i)
                return


def is_a_header_rule(s):
    """
    Decides if a (stripped, non-empty) line is a - or = header.
    """

    first_char = None
    for ch in s:
        if not first_char:
            if ch not in "-=":
                return False
            first_char = ch
            continue
        if ch != first_char:
            return False
    return True


def format_body(input, col):
    """
    Wrap paragraphs up to column number `col`. A markdown-like syntax is
    supported.

    Returns a list of lines.

    If `col` is negative, don't wrap the lines at all.
    """

    if col < 0:
        return input.splitlines()

    para_lines = []  # Buffer up lines to be wrapped here
    out_lines = []   # Completed wrapped lines eventually go here
    in_triples = False
    in_list = False
    newline_on_next = False

    def flush_para(last_para=False):
        nonlocal in_list, newline_on_next
        if para_lines:
            out_lines.extend(textwrap.wrap("\n".join(para_lines), col))
            del para_lines[:]
            if not last_para:
                out_lines.append("")
        in_list = False
        newline_on_next = False

    for line in input.splitlines():
        if newline_on_next:
            out_lines.append("")
            newline_on_next = False

        words = line.split()

        if line == "```":
            # verbatim ``` block start/end
            if not in_triples:
                flush_para()
                out_lines.append("/")
            else:
                out_lines.extend(["\\"])
                newline_on_next = True
            in_triples = not in_triples
        elif in_triples:
            out_lines.append("| " + line)
        elif not line.strip():
            # An empty line marks the end of a paragraphs and a bullet list
            if in_list:
                in_list = False
                newline_on_next = True
            else:
                flush_para()
        elif line.startswith(("http://", "https://")):
            # Lines starting with URLs are preserved
            out_lines.append(line)
        elif all([ch == "#" for ch in words[0]]):
            # A h1/h2/...
            flush_para()
            out_lines.append(line)
            out_lines.append('-' * len(line))
            out_lines.append("")
        elif line.lstrip().startswith(("-", "*")):
            # A bullet list item
            out_lines.append(line)  # preserve indent!
            in_list = True
        elif in_list:
            # If we are still in a list then pass the line right through
            out_lines.append(line)
        else:
            # Otherwise buffer the line for wrapping
            para_lines.append(" ".join(words))
    flush_para(True)
    return out_lines


if __name__ == "__main__":
    # Handle all environment variables here
    if os.environ.get("J_JOURNAL_DEBUG"):
        logging.root.setLevel(logging.DEBUG)

    colour_env = os.environ.get("J_JOURNAL_COLOURS", None)
    if colour_env:
        colours = Colours.from_str(colour_env)
    else:
        colours = Colours()

    try:
        jrnl_dir = os.environ["J_JOURNAL_DIR"]
    except KeyError:
        print_err("Please set J_JOURNAL_DIR")
        sys.exit(1)

    wrap_col = os.environ.get("J_JOURNAL_WRAP_COL", DEFAULT_WRAP_COL)
    try:
        wrap_col = int(wrap_col)
    except ValueError:
        print_err("Invalid J_JOURNAL_WRAP_COL environment")
        sys.exit(1)
    time_filter = os.environ.get("J_JOURNAL_TIME")
    editor = os.environ.get("EDITOR", DEFAULT_EDITOR)
    pager = os.environ.get("J_JOURNAL_PAGER", DEFAULT_PAGER)

    jrnl = Journal(jrnl_dir, colours=colours, editor=editor, pager=pager,
                   wrap_col=wrap_col)

    # Command line interface
    parser = argparse.ArgumentParser(
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers()

    new_parser = subparsers.add_parser('new', aliases=['n'])
    new_parser.set_defaults(mode='new')

    edit_parser = subparsers.add_parser('edit', aliases=['e'])
    edit_parser.set_defaults(mode='edit')
    edit_parser.add_argument("arg", nargs="*",
                             help="entry id or @tag to edit. "
                                  "An id of '^N' edits the Nth newest entry.")

    show_parser = subparsers.add_parser('show', aliases=['s'])
    show_parser.set_defaults(mode='show')
    show_parser.add_argument("arg", nargs="*",
                             help="an id to show or a @tag to filter by. "
                             "If omitted, shows all entries matching filters.")
    show_parser.add_argument("--short", "-s", action="store_true",
                             help="omit entry bodies.")
    show_parser.add_argument("--term", "-t", action="append", default=None,
                             help="Filter by textual search terms.")
    show_parser.add_argument("--when", "-w", default=time_filter,
                             help="Filter by time. See TIME FORMATS in the "
                             "top-level help string for the syntax.")
    show_parser.add_argument("--json", "-j", action="store_true",
                             help="Output in JSON format")
    show_parser.add_argument("--case-sensitive", "-c", action="store_true",
                             help="Make textual filters case sensitive")

    # Running with no args displays the journal, same as 'j s'
    if len(sys.argv[1:]) == 0:
        sys.argv.append("show")

    args = parser.parse_args()
    try:
        mode = args.mode
    except AttributeError:
        parser.print_help()
        sys.exit(1)

    if mode == "new":
        jrnl.new_entry()
    elif mode == "show":
        if all([not a.startswith("@") for a in args.arg]):
            # User is passing a list of entry IDs.
            tag_filters = []
            id_filters = args.arg
        elif all([a.startswith("@") for a in args.arg]):
            # user is passing a list of tags.
            tag_filters = [x[1:] for x in args.arg]
            id_filters = []
        else:
            print("Positional arguments must all be @tags or all be entry IDs")
            sys.exit(1)

        # Setup filters
        if args.when:
            try:
                time_filter = TimeFilter.from_arg(args.when)
            except TimeFilterException as e:
                print("invalid time filter: %s" % e)
                sys.exit(1)
        else:
            time_filter = TimeFilter()

        textual_filters = args.term
        filters = FilterSettings(
            tag_filters=tag_filters,
            textual_filters=textual_filters,
            time_filter=time_filter,
            id_filters=id_filters,
            case_sensitive=args.case_sensitive,
        )
        jrnl.show_entries(bodies=not args.short, filters=filters,
                          output_json=args.json)
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
