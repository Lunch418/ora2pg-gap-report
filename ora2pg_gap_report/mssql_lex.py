"""Shared, deliberately approximate T-SQL (SQL Server) lexical helpers.

The MSSQL-dialect counterpart of plsql_lex.py and mysql_lex.py: not a
real parser, just string/comment-aware masking so keyword search never
matches inside a literal or a comment, plus "what named object contains
this position" attribution. T-SQL's lexical rules differ from both of
the other dialects in ways that matter for correctness:

- Identifiers can be bracket-quoted (`[Order Details]`) -- neither
  Oracle nor MySQL has this. SSMS and `Generate Scripts` bracket-quote
  *every* identifier by default, so essentially all real-world input is
  full of them, and a literal ']' inside such a name is written doubled
  (`]]`), the same way quotes are.
- '--' starts a comment with no trailing-whitespace requirement, unlike
  MySQL (where 'a--b' is subtraction). T-SQL has no '#' comment at all;
  '#' instead prefixes temporary-table names (`#staging`, `##global`).
- Double quotes are *identifier* quotes, not string quotes, under the
  default QUOTED_IDENTIFIER ON -- the Oracle convention, the opposite of
  MySQL's default. They are therefore left untouched, like brackets.
- Backslash is NOT an escape character inside string literals (again
  unlike MySQL): the only escape is the doubled quote (`''`). Masking a
  T-SQL literal with MySQL's rules would end it in the wrong place.
- 'N' prefixes a Unicode literal (`N'text'`); the prefix is an ordinary
  identifier character sequence, so nothing special is needed to mask
  the literal itself, but the prefix must not be swallowed.
- Variables are '@name' and '@@name', and both may appear anywhere an
  expression may -- so '@' is part of the identifier character set here.
"""

import re
from functools import lru_cache

# T-SQL regular identifiers: letter/underscore/@/# to start (covering
# @variable, @@systemvar and #temp names), then letters, digits, '_',
# '@', '#', '$'. Bracket- and double-quote-delimited names can hold
# almost anything, and are matched by qualified_name_pattern()'s own
# optional delimiters around this pattern rather than by IDENTIFIER.
IDENTIFIER = r"[A-Za-z_@#][A-Za-z0-9_@#$]*"


# One name component: bracket-delimited, double-quote-delimited, or bare.
# The delimited forms deliberately accept anything up to their closer,
# not just IDENTIFIER characters -- the entire point of `[Order Details]`
# is that it holds what a bare identifier cannot (spaces, punctuation,
# reserved words), and matching only the IDENTIFIER part would silently
# truncate such a name to its first word.
_NAME_PART = rf"(?:\[[^\]]*\]|\"[^\"]*\"|{IDENTIFIER})"


def qualified_name_pattern(keyword_pattern: str) -> str:
    """Regex source fragment matching `<keyword> [db.][schema.]name`,
    capturing the final name component *with* its delimiters (if any) --
    pass the capture through normalize_name() to get the bare name.
    Mirrors mysql_lex.qualified_name_pattern's contract, with T-SQL's two
    delimiter styles in place of MySQL's backtick, and with the qualifier
    allowed to repeat so a three-part `db.schema.name` matches too."""
    qualifier = rf"(?:{_NAME_PART}\s*\.\s*)*"
    return rf"{keyword_pattern}\s+{qualifier}({_NAME_PART})"


def normalize_name(raw: str) -> str:
    """Strip a name's `[...]`/`"..."` delimiters, undoing T-SQL's doubled
    -delimiter escape. Kept separate from qualified_name_pattern because
    a single regex capture group cannot span alternatives that each need
    a different slice of the match."""
    if len(raw) >= 2 and raw.startswith("[") and raw.endswith("]"):
        return raw[1:-1].replace("]]", "]")
    if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1].replace('""', '"')
    return raw


def _mask(source: str, reveal_strings: bool) -> str:
    """Shared tokenizer for mask_strings_and_comments() and
    mask_comments_only() -- both views must agree on exactly where every
    comment/string/quoted-identifier starts and ends, or their "same
    length, valid offsets in both" contract could silently break if one
    view's rules drifted from the other's under a future fix. Same
    single-tokenizer-two-flags shape plsql_lex._mask() and
    mysql_lex._mask() already use, for the same reason.
    `reveal_strings=True` keeps string content exactly as written while
    still blanking comments; `reveal_strings=False` blanks both."""
    out = []
    i, n = 0, len(source)
    while i < n:
        two = source[i : i + 2]
        if two == "--":
            # No trailing-whitespace requirement, unlike MySQL.
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if two == "/*":
            # T-SQL block comments nest, unlike Oracle's and MySQL's, so
            # the closing marker is matched by depth rather than by the
            # first '*/' encountered -- otherwise the tail of an outer
            # comment would be treated as live code.
            depth = 0
            while i < n:
                if source[i : i + 2] == "/*":
                    depth += 1
                    out.append("  ")
                    i += 2
                    continue
                if source[i : i + 2] == "*/":
                    depth -= 1
                    out.append("  ")
                    i += 2
                    if depth == 0:
                        break
                    continue
                out.append("\n" if source[i] == "\n" else " ")
                i += 1
            continue
        if source[i] in "[\"":
            # Bracket- and double-quote-delimited identifiers are never
            # masked, in either view -- deliberately, mirroring how
            # plsql_lex.py leaves Oracle's double-quoted identifiers and
            # mysql_lex.py leaves MySQL's backtick-quoted ones untouched.
            # A detector's own IDENTIFIER-based regexes read the real
            # name text straight out of this "masked" view to report
            # object_name, and SSMS bracket-quotes every identifier by
            # default, so blanking them would break name attribution for
            # essentially all real-world input. What this branch does do:
            # recognise the span, so a '--' or a quote that happens to
            # appear *inside* a delimited name (legal: `[my--col]`) isn't
            # misread as starting a comment or a string. A literal
            # delimiter inside a name is written doubled (']]', '""'),
            # matching T-SQL's own escaping rule.
            closer = "]" if source[i] == "[" else '"'
            start = i
            i += 1
            while i < n:
                if source[i] == closer:
                    if source[i : i + 2] == closer * 2:
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            out.append(source[start:i])
            continue
        if source[i] == "'":
            out.append("'" if reveal_strings else " ")
            i += 1
            while i < n:
                if source[i] == "'":
                    # Doubled quote is the ONLY escape in T-SQL: there is
                    # no backslash escaping here, unlike MySQL.
                    if source[i : i + 2] == "''":
                        out.append("''" if reveal_strings else "  ")
                        i += 2
                        continue
                    out.append("'" if reveal_strings else " ")
                    i += 1
                    break
                out.append(source[i] if reveal_strings else ("\n" if source[i] == "\n" else " "))
                i += 1
            continue
        out.append(source[i])
        i += 1
    return "".join(out)


@lru_cache(maxsize=8)
def mask_strings_and_comments(source: str) -> str:
    """Replace comment and string-literal contents with spaces,
    preserving length and newlines, so absolute offsets and line numbers
    stay valid and keyword regexes never match inside a literal or a
    comment. Bracket- and double-quote-delimited identifiers are passed
    through untouched (see _mask's own comment for why).

    Cached -- same reasoning as the other two dialects' lexers: every
    MSSQL detector calls this with the same `source` for a given scanned
    file, so caching collapses what would otherwise be an O(n) pass
    repeated once per detector."""
    return _mask(source, reveal_strings=False)


@lru_cache(maxsize=8)
def mask_comments_only(source: str) -> str:
    """Blank out comments only, leaving string-literal content exactly as
    written. Needed by any detector whose subject matter is a literal's
    own content, which must not already be blanked by the safe view while
    still not matching inside commented-out code.

    Same length- and newline-preserving contract as the other view,
    produced by the same tokenizer, so offsets found here stay valid for
    line_at() and enclosing_object_name_index() built from the safe view."""
    return _mask(source, reveal_strings=True)


def line_at(text: str, pos: int) -> int:
    """1-indexed line number of `pos` within `text`."""
    return text.count("\n", 0, pos) + 1


def skip_balanced_parens(text: str, start: int) -> int:
    """`start` points at '('; returns the index just after the matching
    ')'. Parenthesis nesting isn't dialect-specific."""
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)


def table_column_definition_list(text: str, table_name_end: int) -> tuple[int, int] | None:
    """Given the end of 'CREATE TABLE [schema.]name', the (open_paren_pos,
    close_paren_pos) span of the column-definition list's own '(...)'.
    Same contract as the other dialects' version -- T-SQL parenthesises
    its column list the same way, and the trailing table options (ON
    [PRIMARY], WITH (...), TEXTIMAGE_ON ...) sit after the closing paren,
    which this function stops at."""
    pos = table_name_end
    while pos < len(text) and text[pos] in " \t\r\n":
        pos += 1
    if pos >= len(text) or text[pos] != "(":
        return None
    close = skip_balanced_parens(text, pos) - 1
    return pos, close


# CREATE and ALTER both introduce a routine body worth attributing to --
# an ALTER PROCEDURE script is just as common in real T-SQL as a CREATE,
# and 'CREATE OR ALTER' is the modern spelling of both at once.
_CREATE_PREFIX = r"(?:CREATE(?:\s+OR\s+ALTER)?|ALTER)\s+"
_TABLE_NAME_RE = re.compile(qualified_name_pattern(r"CREATE\s+TABLE"), re.IGNORECASE)
_PROCEDURE_NAME_RE = re.compile(
    qualified_name_pattern(_CREATE_PREFIX + r"PROC(?:EDURE)?"), re.IGNORECASE
)
_FUNCTION_NAME_RE = re.compile(qualified_name_pattern(_CREATE_PREFIX + "FUNCTION"), re.IGNORECASE)
_TRIGGER_NAME_RE = re.compile(qualified_name_pattern(_CREATE_PREFIX + "TRIGGER"), re.IGNORECASE)
_VIEW_NAME_RE = re.compile(qualified_name_pattern(_CREATE_PREFIX + "VIEW"), re.IGNORECASE)


@lru_cache(maxsize=8)
def enclosing_object_name_index(text: str) -> tuple[tuple[int, str, str], ...]:
    """Every 'named container' start position in `text` (already masked),
    tagged by kind ('table' / 'procedure' / 'function' / 'trigger' /
    'view'), sorted by position. Deliberately simpler than the Oracle
    version, like the MySQL one: T-SQL has no PACKAGE construct, so every
    routine is its own top-level CREATE and there is no package-name
    prefix or nested-routine bookkeeping to do."""
    tagged = (
        [(m.start(), "table", normalize_name(m.group(1)).upper()) for m in _TABLE_NAME_RE.finditer(text)]
        + [(m.start(), "procedure", normalize_name(m.group(1)).upper()) for m in _PROCEDURE_NAME_RE.finditer(text)]
        + [(m.start(), "function", normalize_name(m.group(1)).upper()) for m in _FUNCTION_NAME_RE.finditer(text)]
        + [(m.start(), "trigger", normalize_name(m.group(1)).upper()) for m in _TRIGGER_NAME_RE.finditer(text)]
        + [(m.start(), "view", normalize_name(m.group(1)).upper()) for m in _VIEW_NAME_RE.finditer(text)]
    )
    return tuple(sorted(tagged, key=lambda t: t[0]))


def enclosing_object_name(index: tuple[tuple[int, str, str], ...], position: int) -> str:
    """The name of whichever container (table/procedure/function/trigger/
    view) starts most recently before `position` -- 'UNKNOWN' if nothing
    precedes at all."""
    current: str | None = None
    for pos, _kind, name in index:
        if pos > position:
            break
        current = name
    return current or "UNKNOWN"
