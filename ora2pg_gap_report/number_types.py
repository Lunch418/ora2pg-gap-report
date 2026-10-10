"""Where Oracle source declares a numeric type, and what ora2pg 25.0
turns it into with its default configuration -- shared by the detectors
for GAP-130..132 (number_without_precision, number_as_float,
integer_division).

ora2pg's mapping (Ora2Pg/Oracle.pm, _sql_type, with the ora2pg.conf it
ships: PG_NUMERIC_TYPE 1, PG_INTEGER_TYPE 1, DEFAULT_NUMERIC bigint):

- NUMBER with no precision -> bigint, in a column, a variable, a
  parameter or a return type alike;
- NUMBER(p) or NUMBER(p, 0) -> smallint (p < 5), integer (p <= 9),
  bigint (p <= 19), numeric(p) above that;
- NUMBER(p, s) with 0 < s <= p: p <= 6 -> real in PL/SQL (a column gets
  decimal(p, s)), p <= 15 -> double precision, decimal(p, s) above that;
- FLOAT -> double precision; INTEGER, INT, SMALLINT, PLS_INTEGER,
  BINARY_INTEGER -> integer or smallint.

Checked by running ora2pg 25.0 on the declarations, see
docs/research/gap-130-number-without-precision.md and the two after it.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from .lex_common import table_column_definition_list
from .plsql_lex import IDENTIFIER, TABLE_HEAD, enclosing_object_name, enclosing_object_name_index, qualified_name_pattern

_TYPE = (
    r"(?P<type>NUMBER(?:\s*\(\s*(?P<precision>\d+|\*)\s*(?:,\s*(?P<scale>-?\d+)\s*)?\))?"
    r"|FLOAT(?:\s*\(\s*\d+\s*\))?|INTEGER|INT|SMALLINT|BIGINT|PLS_INTEGER|BINARY_INTEGER)(?![\w$#])"
)
# Words that can stand before a type without naming what is declared.
_NOT_A_NAME = (
    r"(?!(?:AS|IS|OF|RETURN|SELECT|THEN|ELSE|WHEN|AND|OR|NOT|IN|OUT|BY|INTO|FROM|WHERE|NOCOPY|CONSTANT)\b)"
)
_DECLARATION_RE = re.compile(
    # v NUMBER, p IN OUT NOCOPY NUMBER, c CONSTANT NUMBER, a column
    rf"(?<![\w$#.%])(?P<name>{_NOT_A_NAME}{IDENTIFIER})\s+(?:CONSTANT\s+)?"
    rf"(?:IN\s+OUT\s+|IN\s+|OUT\s+)?(?:NOCOPY\s+)?{_TYPE}"
    # RETURN NUMBER, in a routine's header
    rf"|\bRETURN\s+{_TYPE.replace('?P<type>', '?P<rtype>').replace('?P<precision>', '?P<rprecision>').replace('?P<scale>', '?P<rscale>')}"
    # SUBTYPE money IS NUMBER(10,2), TYPE t IS TABLE OF NUMBER
    rf"|\b(?:SUB)?TYPE\s+{IDENTIFIER}\s+IS\s+(?:TABLE\s+OF\s+|VARRAY\s*\(\s*\d+\s*\)\s+OF\s+)?"
    rf"{_TYPE.replace('?P<type>', '?P<stype>').replace('?P<precision>', '?P<sprecision>').replace('?P<scale>', '?P<sscale>')}",
    re.IGNORECASE,
)
_TABLE_RE = re.compile(qualified_name_pattern(TABLE_HEAD), re.IGNORECASE)
# BIGINT is not an Oracle type: it is read so the detectors find their
# constructs again in ora2pg's output (--verify).
_INTEGER_WORDS = {"INTEGER", "INT", "SMALLINT", "BIGINT", "PLS_INTEGER", "BINARY_INTEGER"}


@dataclass(frozen=True)
class Declaration:
    """One use of a numeric type in a declaration."""

    position: int  # where the type starts
    name: str | None  # what is declared; None for a RETURN or a (SUB)TYPE
    type_text: str  # as written, whitespace collapsed
    object_name: str  # the table for a column, else the enclosing object
    in_table: bool  # a column of a CREATE TABLE
    pg_type: str  # what ora2pg 25.0 makes of it by default


def _pg_type(base: str, precision: str | None, scale: str | None, in_table: bool) -> str:
    base = base.upper()
    if base.startswith("FLOAT"):
        return "double precision"
    if base in _INTEGER_WORDS:
        return {"SMALLINT": "smallint", "BIGINT": "bigint"}.get(base, "integer")
    if precision is None:
        return "bigint"
    if precision == "*":
        return "numeric" if not scale or scale == "0" else f"decimal(38,{scale})"
    p = int(precision)
    s = int(scale) if scale is not None else 0
    if s == 0:
        if p < 5:
            return "smallint"
        if p <= 9:
            return "integer"
        if p <= 19:
            return "bigint"
        return f"numeric({p})"
    if 0 < s <= p:
        if p <= 6:
            return f"decimal({p},{s})" if in_table else "real"
        if p <= 15:
            return "double precision"
    return f"decimal({p},{s})" if s <= p else "numeric"


def _table_spans(clean: str) -> list[tuple[int, int, str]]:
    spans = []
    for m in _TABLE_RE.finditer(clean):
        columns = table_column_definition_list(clean, m.end())
        if columns is not None:
            spans.append((columns[0], columns[1], m.group(1).upper()))
    return spans


def declarations(clean: str) -> Iterator[Declaration]:
    """Every numeric type declared in masked `clean`, in order."""
    if not re.search(r"NUMBER|FLOAT|INT", clean, re.IGNORECASE):
        return
    tables = _table_spans(clean)
    index = enclosing_object_name_index(clean)
    for m in _DECLARATION_RE.finditer(clean):
        if m.group("type") is not None:
            group, name = "", m.group("name")
        elif m.group("rtype") is not None:
            group, name = "r", None
        else:
            group, name = "s", None
        start = m.start(f"{group}type")
        table = next((t for t in tables if t[0] < start < t[1]), None)
        yield Declaration(
            position=start,
            name=name,
            type_text=" ".join(m.group(f"{group}type").split()),
            object_name=table[2] if table else enclosing_object_name(index, start),
            in_table=table is not None,
            pg_type=_pg_type(
                re.match(r"[A-Za-z_]+", m.group(f"{group}type")).group(0),  # type: ignore[union-attr]
                m.group(f"{group}precision"),
                m.group(f"{group}scale"),
                table is not None,
            ),
        )
