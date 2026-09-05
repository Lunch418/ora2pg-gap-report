import re

from .. import mssql_lex
from ..mssql_lex import normalize_name, qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_PATTERN_RE = re.compile(r"\bCOLLATE\s+\w+", re.IGNORECASE)

_DOC = """Detect per-column COLLATE clauses in T-SQL. ora2pg -M drops the
clause and maps the column onto citext, so a case-SENSITIVE source
collation silently becomes case-insensitive -- verified on live data.
See docs/research/gap-103-mssql-collation.md."""

SPEC = DetectorSpec(
    name="mssql_collation",
    dialect="mssql",
    severity="high",
    pattern=_PATTERN_RE,
    strategy=TABLE_COLUMNS,
    snippet=lambda m: m.group(0),
    statement_pattern=_TABLE_RE,
    normalize_object_name=normalize_name,
)

find_mssql_collations = build(SPEC, mssql_lex)
find_mssql_collations.__doc__ = _DOC
