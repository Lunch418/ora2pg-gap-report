import re

from .. import mysql_lex
from ..mysql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_COLLATE_RE = re.compile(r"\b(COLLATE|CHARACTER\s+SET)\s+\w+", re.IGNORECASE)

_DOC = """Detect per-column COLLATE/CHARACTER SET clauses in a MySQL CREATE
TABLE. ora2pg -m drops them, silently turning MySQL's usual
case-insensitive collation into PostgreSQL's case-sensitive default --
no error, just different query results. See docs/research/
gap-085-mysql-collate.md."""

SPEC = DetectorSpec(
    name="mysql_collate",
    dialect="mysql",
    severity="high",
    pattern=_COLLATE_RE,
    strategy=TABLE_COLUMNS,
    snippet=lambda m: m.group(0),
    statement_pattern=_TABLE_RE,
)

find_mysql_collations = build(SPEC, mysql_lex)
find_mysql_collations.__doc__ = _DOC
