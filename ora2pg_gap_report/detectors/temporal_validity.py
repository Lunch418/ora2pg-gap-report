import re

from .. import plsql_lex
from ..plsql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, STATEMENT_CLAUSE, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
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

SPEC = DetectorSpec(
    name="temporal_validity",
    dialect="oracle",
    severity="high",
    pattern=_PERIOD_FOR_RE,
    strategy=STATEMENT_CLAUSE,
    snippet=lambda m: re.sub(r"\s+", " ", m.group(0).strip().upper()),
    statement_pattern=_TABLE_RE,
)

find_temporal_validity = build(SPEC, plsql_lex)
find_temporal_validity.__doc__ = _DOC
