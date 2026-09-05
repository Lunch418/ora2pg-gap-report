import re

from .. import mssql_lex
from ..mssql_lex import normalize_name, qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_PATTERN_RE = re.compile(r"\bROWVERSION\b", re.IGNORECASE)

_DOC = """Detect T-SQL ROWVERSION columns. ora2pg -M maps them onto a
plain bytea, which never changes on its own, so optimistic-locking
checks built on the column silently stop detecting conflicts. See
docs/research/gap-105-mssql-rowversion.md."""

SPEC = DetectorSpec(
    name="mssql_rowversion",
    dialect="mssql",
    severity="high",
    pattern=_PATTERN_RE,
    strategy=TABLE_COLUMNS,
    snippet='ROWVERSION',
    table_pattern=_TABLE_RE,
    normalize_table_name=normalize_name,
)

find_mssql_rowversion_columns = build(SPEC, mssql_lex)
find_mssql_rowversion_columns.__doc__ = _DOC
