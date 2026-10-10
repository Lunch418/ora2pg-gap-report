"""What a scan cannot see: SQL built while the program runs.

`EXECUTE IMMEDIATE v_sql`, `OPEN c FOR v_sql`, `DBMS_SQL.PARSE(c, v_sql)`,
MySQL's `PREPARE s FROM @sql`, T-SQL's `EXEC(@sql)` and `sp_executesql
@sql` run a statement whose text is only known at run time. No reading
of the source can check it: a gap inside it is found by running it, or
not at all.

These are not findings. They do not count toward a severity, a stage,
the effort estimate or --fail-on, because nothing is known to be wrong
with them; they are the list of places the report says nothing about,
so that silence is not taken for "checked". Two kinds:

- `partial`: the text is put together from string literals and
  something else (`'SELECT * FROM ' || v_table`). The literal parts are
  scanned as usual (see plsql_lex.mask_dynamic_sql_visible); what the
  variables add is not.
- not partial: the whole text comes from a variable, a function or a
  table, and none of it is scanned.

SQL made only of literals (`EXECUTE IMMEDIATE 'TRUNCATE TABLE t'`) is
scanned in full and is not listed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from . import mssql_lex, mysql_lex, plsql_lex
from .lex_common import line_at, skip_balanced_parens


@dataclass(frozen=True, slots=True)
class Unchecked:
    """One statement whose SQL text is built at run time."""

    kind: str  # execute_immediate | open_for | dbms_sql_parse | prepare | exec | sp_executesql
    object_name: str
    line: int
    snippet: str
    partial: bool
    source_file: str = ""


def explanation(unchecked: "list[Unchecked]", lang: str) -> str:
    """What the reports say under the heading: why these are listed, and
    what "partly" means when any of them is."""
    from . import i18n

    text = i18n.t(lang, "unchecked_text")
    if any(u.partial for u in unchecked):
        text += " " + i18n.t(lang, "unchecked_partial_text")
    return text


_SNIPPET_LENGTH = 80

# Oracle. Each pattern ends where the SQL text starts -- before the
# whitespace, which in the masked view may be a blanked literal.
_EXECUTE_IMMEDIATE_RE = re.compile(r"\bEXECUTE\s+IMMEDIATE\b", re.IGNORECASE)
_OPEN_FOR_RE = re.compile(rf"\bOPEN\s+{plsql_lex.IDENTIFIER}(?:\s*\.\s*{plsql_lex.IDENTIFIER})?\s+FOR\b", re.IGNORECASE)
_STATIC_QUERY_RE = re.compile(r"[\s(]*(?:SELECT|WITH)\b", re.IGNORECASE)
_DBMS_SQL_PARSE_RE = re.compile(r"\b(?:SYS\s*\.\s*)?DBMS_SQL\s*\.\s*PARSE\s*(?=\()", re.IGNORECASE)
_COMMA_RE = re.compile(",")
_ARGUMENT_END_RE = re.compile(r",|\)")
# Where the text of an EXECUTE IMMEDIATE or OPEN ... FOR ends.
_ORACLE_TEXT_END_RE = re.compile(r";|\b(?:INTO|USING|RETURNING|RETURN|BULK)\b", re.IGNORECASE)

# MySQL: PREPARE s FROM <text>.
_PREPARE_RE = re.compile(r"\bPREPARE\s+[A-Za-z0-9_$`]+\s+FROM\b", re.IGNORECASE)
_MYSQL_TEXT_END_RE = re.compile(r";|\$\$|//|\n\s*\n")

# T-SQL: EXEC(<text>), EXECUTE(<text>), sp_executesql <text>[, ...].
_EXEC_RE = re.compile(r"\bEXEC(?:UTE)?\s*(?=\()", re.IGNORECASE)
_SP_EXECUTESQL_RE = re.compile(r"\b(?:EXEC(?:UTE)?\s+)?(?:\[?(?:sys|dbo)\]?\s*\.\s*)?\[?sp_executesql\]?(?![\w\]])", re.IGNORECASE)
_MSSQL_TEXT_END_RE = re.compile(r";|,|\n")

# What is left of a text made only of literals once they are blanked:
# operators that join them, parentheses, T-SQL's N prefix.
_JOINERS_RE = re.compile(r"\|\||\+|[()\s]|\bN\b", re.IGNORECASE)


def _text_end(clean: str, start: int, end_re: re.Pattern[str]) -> int:
    """Where the SQL text that starts at `start` ends: the first `end_re`
    match outside parentheses, or the end of `clean`."""
    i = start
    while True:
        m = end_re.search(clean, i)
        stop = m.start() if m else len(clean)
        paren = clean.find("(", i, stop)
        if paren == -1:
            return stop
        i = skip_balanced_parens(clean, paren)
        if i <= paren:  # unbalanced: give up at the parenthesis
            return paren


def _site(
    clean: str,
    readable: str,
    statement: int,
    start: int,
    end: int,
    kind: str,
    name: str,
    shown_to: int | None = None,
) -> Unchecked | None:
    """The run-time text clean[start:end] as an Unchecked, or None if it
    is made only of string literals -- or is empty, as in a statement cut
    off at the end of the file. The snippet runs from `statement` to
    `shown_to` (default `end`)."""
    rest = _JOINERS_RE.sub("", clean[start:end])
    if not rest:
        return None
    snippet = " ".join(readable[statement : shown_to or end].split())
    if len(snippet) > _SNIPPET_LENGTH:
        snippet = snippet[: _SNIPPET_LENGTH - 3].rstrip() + "..."
    return Unchecked(
        kind=kind,
        object_name=name,
        line=line_at(clean, statement),
        snippet=snippet,
        partial="'" in readable[start:end],
    )


def _oracle(source: str) -> list[Unchecked]:
    upper = source.upper()
    if "IMMEDIATE" not in upper and " FOR " not in upper and "DBMS_SQL" not in upper:
        return []
    clean = plsql_lex.mask_strings_and_comments(source)
    readable = plsql_lex.mask_comments_only(source)
    index = plsql_lex.enclosing_object_name_index(clean)
    sites: list[Unchecked] = []

    def add(statement: int, start: int, end: int, kind: str, shown_to: int | None = None) -> None:
        name = plsql_lex.enclosing_object_name(index, statement)
        site = _site(clean, readable, statement, start, end, kind, name, shown_to)
        if site is not None:
            sites.append(site)

    for m in _EXECUTE_IMMEDIATE_RE.finditer(clean):
        add(m.start(), m.end(), _text_end(clean, m.end(), _ORACLE_TEXT_END_RE), "execute_immediate")
    for m in _OPEN_FOR_RE.finditer(clean):
        if _STATIC_QUERY_RE.match(clean, m.end()):
            continue
        add(m.start(), m.end(), _text_end(clean, m.end(), _ORACLE_TEXT_END_RE), "open_for")
    for m in _DBMS_SQL_PARSE_RE.finditer(clean):
        close = skip_balanced_parens(clean, m.end())
        # The second argument: after the first comma outside parentheses.
        comma = _text_end(clean, m.end() + 1, _COMMA_RE)
        if comma >= close - 1:
            continue
        add(m.start(), comma + 1, _text_end(clean, comma + 1, _ARGUMENT_END_RE), "dbms_sql_parse", close)
    return sites


def _mysql(source: str) -> list[Unchecked]:
    if "PREPARE" not in source.upper():
        return []
    clean = mysql_lex.mask_strings_and_comments(source)
    readable = mysql_lex.mask_comments_only(source)
    index = mysql_lex.enclosing_object_name_index(clean)
    sites = []
    for m in _PREPARE_RE.finditer(clean):
        end = _text_end(clean, m.end(), _MYSQL_TEXT_END_RE)
        site = _site(clean, readable, m.start(), m.end(), end, "prepare", mysql_lex.enclosing_object_name(index, m.start()))
        if site is not None:
            sites.append(site)
    return sites


def _mssql(source: str) -> list[Unchecked]:
    upper = source.upper()
    if "EXEC" not in upper:
        return []
    clean = mssql_lex.mask_strings_and_comments(source)
    readable = mssql_lex.mask_comments_only(source)
    index = mssql_lex.enclosing_object_name_index(clean)
    sites = []

    def add(statement: int, start: int, end: int, kind: str, shown_to: int | None = None) -> None:
        name = mssql_lex.enclosing_object_name(index, statement)
        site = _site(clean, readable, statement, start, end, kind, name, shown_to)
        if site is not None:
            sites.append(site)

    for m in _EXEC_RE.finditer(clean):
        close = skip_balanced_parens(clean, m.end())
        add(m.start(), m.end() + 1, max(m.end() + 1, close - 1), "exec", close)
    for m in _SP_EXECUTESQL_RE.finditer(clean):
        add(m.start(), m.end(), _text_end(clean, m.end(), _MSSQL_TEXT_END_RE), "sp_executesql")
    return sites


_BY_DIALECT: dict[str, Callable[[str], list[Unchecked]]] = {"oracle": _oracle, "mysql": _mysql, "mssql": _mssql}


def find_unchecked(source: str, dialect: str = "oracle") -> list[Unchecked]:
    """Every statement in `source` whose SQL is built at run time, in the
    order they appear."""
    finder = _BY_DIALECT.get(dialect)
    if finder is None:
        return []
    sites = finder(source)
    sites.sort(key=lambda s: s.line)
    return sites

