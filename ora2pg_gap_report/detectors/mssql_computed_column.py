import re

from .. import mssql_lex
from ..mssql_lex import normalize_name, qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_PATTERN_RE = re.compile(r"\bAS\s*\(", re.IGNORECASE)

_DOC = """Detect T-SQL computed columns (`col AS (expr)`, with or without
PERSISTED). ora2pg -M builds a BEFORE trigger for them but types the
column as citext regardless of what the expression computes, so a
numeric computation ends up stored as case-insensitive text. See
docs/research/gap-104-mssql-computed-column.md."""

SPEC = DetectorSpec(
    name="mssql_computed_column",
    dialect="mssql",
    severity="high",
    pattern=_PATTERN_RE,
    strategy=TABLE_COLUMNS,
    snippet='AS (...)',
    table_pattern=_TABLE_RE,
    normalize_table_name=normalize_name,
)

find_mssql_computed_columns = build(SPEC, mssql_lex)
find_mssql_computed_columns.__doc__ = _DOC
