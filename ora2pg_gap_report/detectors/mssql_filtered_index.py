import re

from .. import mssql_lex
from ..detector_spec import DetectorSpec, build

# A filtered index is a CREATE INDEX carrying a WHERE clause; the
# bounded non-greedy body keeps the match inside one statement.
_PATTERN_RE = re.compile(r"\bCREATE\s+(?:UNIQUE\s+)?(?:CLUSTERED\s+|NONCLUSTERED\s+)?INDEX\b[^;]{0,300}?\bWHERE\b", re.IGNORECASE)

_DOC = """Detect T-SQL filtered indexes (`CREATE INDEX ... WHERE ...`).
ora2pg -M drops the whole statement, emitting no index at all, even
though PostgreSQL supports partial indexes with the same syntax. See
docs/research/gap-101-mssql-filtered-index.md."""

SPEC = DetectorSpec(
    name="mssql_filtered_index",
    dialect="mssql",
    severity="high",
    pattern=_PATTERN_RE,
    snippet='filtered INDEX',
)

find_mssql_filtered_indexes = build(SPEC, mssql_lex)
find_mssql_filtered_indexes.__doc__ = _DOC
