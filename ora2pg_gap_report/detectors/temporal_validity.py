import re

from .. import plsql_lex
from ..models import Finding
from ..plsql_lex import IDENTIFIER, TABLE_HEAD, line_at, mask_strings_and_comments, qualified_name_pattern
from ..detector_spec import DetectorSpec, STATEMENT_CLAUSE, build

_TABLE_RE = re.compile(
    qualified_name_pattern(TABLE_HEAD),
    re.IGNORECASE,
)
# PERIOD FOR <name> [(<start>, <end>)] -- the period name is required, the
# explicit column pair is optional (Oracle generates hidden columns when
# it's omitted). Requiring the name after FOR keeps an ordinary column
# named `period` out of the match.
_PERIOD_FOR_RE = re.compile(r"\bPERIOD\s+FOR\s+[A-Za-z_][A-Za-z0-9_$#]*", re.IGNORECASE)

_DOC = """Detect Oracle's PERIOD FOR (12c temporal validity) clause in a
CREATE TABLE. ora2pg mangles it into a truncated `period FOR`
fragment inside the column list, so the generated CREATE TABLE
itself fails to load. See
docs/research/gap-045-temporal-validity.md.

object_name is the table's own name (schema-level DDL) -- same
reasoning as index_organized_table.py, whose statement_end() scoping
this mirrors."""

# DBMS_METADATA.GET_DDL's spelling: the period is not part of the CREATE
# TABLE but a separate `ALTER TABLE "S"."T" ADD PERIOD FOR "P"(...)` after
# it. ora2pg drops that statement entirely, so this form is not the
# load failure the CREATE TABLE form is, but a silent loss.
_ALTER_ADD_PERIOD_RE = re.compile(
    qualified_name_pattern(r"\bALTER\s+TABLE") + rf'\s+ADD\s+PERIOD\s+FOR\s+"?{IDENTIFIER}"?',
    re.IGNORECASE,
)

SPEC = DetectorSpec(
    name="temporal_validity",
    dialect="oracle",
    severity="high",
    pattern=_PERIOD_FOR_RE,
    strategy=STATEMENT_CLAUSE,
    snippet=lambda m: re.sub(r"\s+", " ", m.group(0).strip().upper()),
    statement_pattern=_TABLE_RE,
)

_find_in_create_table = build(SPEC, plsql_lex)


def find_temporal_validity(source: str) -> list[Finding]:
    clean = mask_strings_and_comments(source)
    return _find_in_create_table(source) + [
        Finding(
            detector="temporal_validity",
            severity="high",
            object_name=m.group(1).upper(),
            line=line_at(clean, m.start()),
            snippet="ALTER TABLE ... ADD PERIOD FOR",
            message_id="temporal_validity.alter",
        )
        for m in _ALTER_ADD_PERIOD_RE.finditer(clean)
    ]


find_temporal_validity.__doc__ = _DOC + """

The same period in DBMS_METADATA.GET_DDL's spelling -- a separate
ALTER TABLE ... ADD PERIOD FOR after the CREATE TABLE -- is flagged with
its own message: ora2pg drops that statement without a word, so there
the period is lost silently instead of breaking the load."""
