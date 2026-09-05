import re

from .. import mssql_lex
from ..detector_spec import DetectorSpec, build

_PATTERN_RE = re.compile(r"\bTOP\s*\(?\s*(?:\d+|@\w+)", re.IGNORECASE)

_DOC = """Detect T-SQL's TOP n clause. ora2pg -M copies it through
unchanged and PostgreSQL has no TOP at all, so the containing routine
loads cleanly and fails on its first call. See docs/research/
gap-095-mssql-top-clause.md."""

SPEC = DetectorSpec(
    name="mssql_top_clause",
    dialect="mssql",
    severity="high",
    pattern=_PATTERN_RE,
    snippet='TOP n',
)

find_mssql_top_clause = build(SPEC, mssql_lex)
find_mssql_top_clause.__doc__ = _DOC
