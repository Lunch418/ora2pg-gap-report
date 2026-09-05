"""Shared, deliberately approximate MySQL/MariaDB lexical helpers.

The MySQL-dialect counterpart of plsql_lex.py: not a real parser, just
string/comment-aware masking so keyword search never matches inside a
literal or a comment, plus "what named object contains this position"
attribution. MySQL's actual lexical rules differ from Oracle's in ways
that matter for correctness, not just cosmetically:

- Identifiers can be backtick-quoted (`` `col` ``) -- Oracle has no such
  syntax, it uses double quotes for the same purpose, and MySQL's
  backtick content must never be scanned for keywords (a column
  literally named `` `end` `` or `` `create` `` is legal and common).
- '#' is a valid single-line comment starter, in addition to '--' (which
  in strict MySQL requires a trailing whitespace/control character to
  count as a comment at all -- 'a--b' is subtraction, not a comment
  start swallowing the rest of the line; that boundary matters here
  because a bare 'x--1' in real code must not have '1' silently masked
  away as if it were a comment).
- Double-quoted strings ('"..."') are ordinary string literals by
  default (ANSI_QUOTES OFF, MySQL's default), not quoted identifiers as
  in Oracle -- must be masked the same as single-quoted ones.
- Backslash is a real escape character inside string literals
  ('\\'' escapes an apostrophe, not just the doubled '' Oracle uses),
  and must be honored or a masking pass would end a literal early on the
  first apostrophe after a backslash.
- No q-quote literals at all (q'[...]') -- an Oracle-only feature, not
  part of this module.
"""

import re
from functools import lru_cache
from .lex_common import (
    flat_enclosing_object_name as enclosing_object_name,
    line_at,
    skip_balanced_parens,
    table_column_definition_list,
)

# MySQL unquoted identifiers: letters, digits, underscore, dollar sign;
# unlike Oracle, MySQL also permits a leading digit as long as the whole
# identifier isn't purely numeric -- rare enough in real schema/procedure
# code (a column or routine named e.g. '2fa_token') that this deliberately
# stays close to Oracle's IDENTIFIER pattern (leading letter/underscore)
# rather than chasing that edge case. A backtick-quoted name (which can
# be almost anything, including a leading digit or a SQL keyword) is
# matched by qualified_name_pattern()'s own optional backtick literals
# around this pattern, not by IDENTIFIER itself.
IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_$]*"


def qualified_name_pattern(keyword_pattern: str) -> str:
    """Regex source fragment matching `<keyword> [schema.]name`, capturing
    the (possibly backtick-quoted) final name component. Mirrors
    plsql_lex.qualified_name_pattern's contract exactly, just swapping
    Oracle's optional double-quote for MySQL's optional backtick."""
    return rf"{keyword_pattern}\s+(?:`?{IDENTIFIER}`?\.)?`?({IDENTIFIER})`?"


def _mask(source: str, reveal_strings: bool) -> str:
    """Shared tokenizer for mask_strings_and_comments() and
    mask_comments_only() -- both views must agree on exactly where every
    comment/string/backtick-identifier starts and ends, or their "same
    length, valid offsets in both" contract could silently break if one
    view's rules drifted from the other's under a future fix. Mirrors the
    single-tokenizer-two-flags shape plsql_lex._mask() already uses, for
    the same reason: a second, independently-written comment-detection
    pass (one per view) is exactly the kind of duplication that lets the
    two silently disagree later, rather than being unable to by
    construction. `reveal_strings=True` keeps string/backtick-identifier
    content exactly as written while still blanking comments;
    `reveal_strings=False` blanks both."""
    out = []
    i, n = 0, len(source)
    while i < n:
        two = source[i : i + 2]
        if two == "--" and i + 2 < n and source[i + 2] in " \t\r\n":
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if source[i] == "#":
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if two == "/*":
            out.append("  ")
            i += 2
            while i < n and source[i : i + 2] != "*/":
                out.append("\n" if source[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append("  ")
                i += 2
            continue
        if source[i] == "`":
            # Backtick-quoted identifiers are never masked, in either
            # view -- deliberately, mirroring how plsql_lex.py leaves
            # Oracle's double-quoted identifiers untouched. A detector's
            # own IDENTIFIER-based regexes (qualified_name_pattern and
            # friends) read the real name text straight out of this
            # "masked" view to report object_name -- mysqldump backtick-
            # quotes every identifier by default, so blanking backtick
            # content the way string literals are blanked would silently
            # break name attribution for essentially all real-world
            # input. What this branch does do: recognize the span so a
            # '--', '#', quote, or block-comment marker that happens to
            # appear *inside* a backtick-quoted name (rare, but legal --
            # `` `my--col` `` is a real identifier) isn't misread as
            # starting a comment or string and corrupting everything
            # after it. A literal backtick inside a name is written
            # doubled ('``'), matching MySQL's own escaping rule.
            start = i
            i += 1
            while i < n:
                if source[i] == "`":
                    if source[i : i + 2] == "``":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            out.append(source[start:i])
            continue
        if source[i] in "'\"":
            quote = source[i]
            out.append(quote if reveal_strings else " ")
            i += 1
            while i < n:
                if source[i] == "\\" and i + 1 < n:
                    # Backslash-escape: the escaped character can never
                    # end the literal, regardless of what it is (matters
                    # most for \' and \" -- an unescaped version of
                    # either would otherwise look like the closing quote).
                    out.append(source[i : i + 2] if reveal_strings else "  ")
                    i += 2
                    continue
                if source[i] == quote:
                    if source[i : i + 2] == quote * 2:
                        out.append(quote * 2 if reveal_strings else "  ")
                        i += 2
                        continue
                    out.append(quote if reveal_strings else " ")
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
    """Replace comment/string-literal/backtick-identifier contents with
    spaces, preserving length and newlines, so absolute offsets and line
    numbers stay valid and keyword regexes never match inside a literal,
    a comment, or a quoted identifier. Backtick identifier *delimiters*
    are kept masked to a single backtick each (not blanked away either),
    so qualified_name_pattern's own backtick-aware capture still lines up
    against this masked view the same way it does against raw source.

    Cached -- same reasoning as plsql_lex.mask_strings_and_comments():
    every MySQL detector calls this with the same `source` for a given
    scanned file, so caching collapses what would otherwise be an O(n)
    pass repeated once per detector."""
    return _mask(source, reveal_strings=False)


@lru_cache(maxsize=8)
def mask_comments_only(source: str) -> str:
    """Blank out comments only, leaving string-literal and
    backtick-identifier content exactly as written. The MySQL-dialect
    mirror of plsql_lex.mask_comments_only() -- needed for the same
    reason: a detector whose subject matter is a literal's own content
    (not yet needed by any MySQL detector, but kept for parity so a
    future one doesn't have to invent this separately) must not have that
    content already blanked out by the safe view, while still not
    matching inside commented-out code.

    Same length- and newline-preserving contract as the other view,
    produced by the same tokenizer, so offsets found here stay valid for
    line_at() and enclosing_object_name_index() built from the safe view.

    Cached -- see mask_strings_and_comments()'s own docstring for why."""
    return _mask(source, reveal_strings=True)


_CREATE_PREFIX = r"CREATE\s+(?:OR\s+REPLACE\s+)?"
_TABLE_NAME_RE = re.compile(qualified_name_pattern(r"CREATE\s+TABLE"), re.IGNORECASE)
_PROCEDURE_NAME_RE = re.compile(qualified_name_pattern(_CREATE_PREFIX + "PROCEDURE"), re.IGNORECASE)
_FUNCTION_NAME_RE = re.compile(qualified_name_pattern(_CREATE_PREFIX + "FUNCTION"), re.IGNORECASE)
_TRIGGER_NAME_RE = re.compile(qualified_name_pattern(_CREATE_PREFIX + "TRIGGER"), re.IGNORECASE)
_VIEW_NAME_RE = re.compile(
    qualified_name_pattern(_CREATE_PREFIX + r"(?:ALGORITHM\s*=\s*\w+\s+)?VIEW"), re.IGNORECASE
)


@lru_cache(maxsize=8)
def enclosing_object_name_index(text: str) -> tuple[tuple[int, str, str], ...]:
    """Every 'named container' start position in `text` (already masked),
    tagged by kind ('table' / 'procedure' / 'function' / 'trigger' /
    'view'), sorted by position. MySQL's mirror of
    plsql_lex.enclosing_object_name_index() -- deliberately simpler,
    because MySQL has no PACKAGE/PACKAGE BODY grouping construct at all
    (every routine is its own top-level CREATE), so there is no
    package-name-prefix or nested-routine bookkeeping to do here."""
    tagged = (
        [(m.start(), "table", m.group(1).upper()) for m in _TABLE_NAME_RE.finditer(text)]
        + [(m.start(), "procedure", m.group(1).upper()) for m in _PROCEDURE_NAME_RE.finditer(text)]
        + [(m.start(), "function", m.group(1).upper()) for m in _FUNCTION_NAME_RE.finditer(text)]
        + [(m.start(), "trigger", m.group(1).upper()) for m in _TRIGGER_NAME_RE.finditer(text)]
        + [(m.start(), "view", m.group(1).upper()) for m in _VIEW_NAME_RE.finditer(text)]
    )
    return tuple(sorted(tagged, key=lambda t: t[0]))



# See plsql_lex's own __all__ for why these are re-exported rather than
# imported from lex_common by each caller.
__all__ = [  # noqa: RUF022
    "IDENTIFIER",
    "qualified_name_pattern",
    "mask_strings_and_comments",
    "mask_comments_only",
    "line_at",
    "skip_balanced_parens",
    "table_column_definition_list",
    "enclosing_object_name_index",
    "enclosing_object_name",
]
