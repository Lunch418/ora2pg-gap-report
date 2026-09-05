"""Lexer primitives that are the same in every dialect, and the
interface a dialect's lexer presents to the detector factory.

The three dialect lexers -- plsql_lex, mysql_lex, mssql_lex -- are
genuinely different where the grammar is different: what a string
literal looks like, how an identifier is quoted, what counts as a
top-level object. But four of their functions were byte-identical
copies, because offsets, newlines and balanced parentheses have nothing
to do with which SQL dialect produced the text.

That mattered more than the line count: line_at()'s O(n^2) fix (see its
docstring) had to be made, and its reasoning written down, three times.
The next such fix would too. Here it exists once, and each dialect
lexer re-exports it so detectors keep talking to their own dialect's
module and nothing about the interface changes.

The flat enclosing_object_name() is shared by MySQL and T-SQL only:
Oracle needs its own, because a routine there can be nested inside a
package body and has to be reported as PACKAGE.ROUTINE.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Callable
from functools import lru_cache
from typing import Protocol

# What enclosing_object_name_index() returns, in every dialect: (offset,
# kind, name) per named object, ordered by offset.
ObjectIndex = tuple[tuple[int, str, str], ...]


@lru_cache(maxsize=8)
def _line_starts(text: str) -> tuple[int, ...]:
    """Offset of the start of each line in `text`, 0-indexed. Backs
    line_at() below -- see that function's docstring for why this exists
    as a separate, cached step rather than counting newlines inline."""
    return (0, *(i + 1 for i, c in enumerate(text) if c == "\n"))


def line_at(text: str, pos: int) -> int:
    """1-indexed line number of `pos` within `text`.

    Every one of this project's detectors calls this once per finding,
    so a whole scan makes O(findings) calls against the same `text`.
    text.count("\\n", 0, pos) -- the obvious one-liner this used to be --
    is O(pos) per call, making the total scan O(n^2) in the size of the
    file (confirmed: 5,720 calls on a 1.6 MB file took 5.6s that way, 155x
    slower than this). Precomputing the newline offsets once per distinct
    `text` (cached the same way mask_strings_and_comments() is, and for
    the same reason -- one `text` in flight per scan_source() call) and
    then binary-searching them per lookup makes each call O(log n)
    instead."""
    return bisect_right(_line_starts(text), pos)


def skip_balanced_parens(text: str, start: int) -> int:
    """`start` points at '('; returns the index just after the matching ')'."""
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
    close_paren_pos) span of the column-definition list's own '(...)' --
    open_paren_pos is the index of the '(' itself, close_paren_pos the
    index of its matching ')' (so the column list's own text is
    text[open_paren_pos + 1 : close_paren_pos]). None if no '(' follows
    the table name at all (only whitespace in between) -- a bare 'CREATE
    TABLE name AS SELECT ...' (a common dedup/diagnostic-table CTAS) has
    no column-type list for a caller to search at all, as opposed to
    'CREATE TABLE name (col_list) AS SELECT ...', which does have one
    (column names only, no types -- those come from the SELECT).

    Exists so a detector matching a column-level clause (a data type
    like ROWID/UROWID, a GENERATED ALWAYS AS (...) VIRTUAL clause) can
    search only the column-definition list itself, not a CTAS's trailing
    AS SELECT clause -- searching past the column list risks misreading
    an unrelated pseudocolumn/alias in the SELECT as if it were a column
    declaration (e.g. 'SELECT ROWID rid, ...' is not a ROWID-typed
    column). Shared rather than reimplemented per detector after the
    identical scoping logic was found duplicated between rowid_type.py
    and virtual_column.py during a code review of the latter."""
    pos = table_name_end
    while pos < len(text) and text[pos] in " \t\r\n":
        pos += 1
    if pos >= len(text) or text[pos] != "(":
        return None
    close = skip_balanced_parens(text, pos) - 1
    return pos, close


def flat_enclosing_object_name(index: ObjectIndex, position: int) -> str:
    """The name of whichever container (table/procedure/function/trigger/
    view) starts most recently before `position` -- 'UNKNOWN' if nothing
    precedes at all. No package-prefix logic needed (see
    enclosing_object_name_index()'s own docstring): every container here
    is already a flat, top-level name."""
    current: str | None = None
    for pos, _kind, name in index:
        if pos > position:
            break
        current = name
    return current or "UNKNOWN"


class Lexer(Protocol):
    """What detector_spec.build() requires of a dialect's lexer module.

    Declared as attributes rather than methods because the things that
    satisfy it are modules, not instances. Its purpose is to make
    build()'s `lex` argument checkable: before this, every call into it
    was an untyped getattr with a `# type: ignore`, so a lexer missing a
    function -- or growing an incompatible signature -- was an
    AttributeError during a real scan rather than an error from mypy.

    Only the universal members are here. `statement_end` and
    `mask_dynamic_sql_visible` are Oracle-only (statement scoping matters
    because DBMS_METADATA.GET_DDL emits no terminating ';', and dynamic
    SQL means EXECUTE IMMEDIATE), so build() checks for those at
    construction time against the strategy that needs them, and says
    which dialect is missing what.
    """

    # Read-only properties rather than plain attributes: a mutable
    # attribute is matched invariantly, which would reject both a
    # function declaring named parameters and an lru_cache-wrapped one --
    # and two of these are cached in every dialect.
    @property
    def mask_strings_and_comments(self) -> Callable[[str], str]: ...

    @property
    def mask_comments_only(self) -> Callable[[str], str]: ...

    @property
    def line_at(self) -> Callable[[str, int], int]: ...

    @property
    def skip_balanced_parens(self) -> Callable[[str, int], int]: ...

    @property
    def table_column_definition_list(self) -> Callable[[str, int], tuple[int, int] | None]: ...

    @property
    def enclosing_object_name_index(self) -> Callable[[str], ObjectIndex]: ...

    @property
    def enclosing_object_name(self) -> Callable[[ObjectIndex, int], str]: ...
