import re

from .. import mssql_lex
from ..detector_spec import DetectorSpec, build

_PATTERN_RE = re.compile(r"\bOUTPUT\s+(?:INSERTED|DELETED)\.", re.IGNORECASE)

_DOC = """Detect T-SQL's OUTPUT INSERTED/DELETED clause. ora2pg -M copies
it through unchanged; PostgreSQL spells the same idea as RETURNING,
so the containing routine loads cleanly and fails on its first call.
See docs/research/gap-097-mssql-output-clause.md."""

SPEC = DetectorSpec(
    name="mssql_output_clause",
    dialect="mssql",
    severity="high",
    pattern=_PATTERN_RE,
    snippet=lambda m: m.group(0).upper(),
)

find_mssql_output_clause = build(SPEC, mssql_lex)
find_mssql_output_clause.__doc__ = _DOC
