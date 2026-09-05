import re

from .. import mssql_lex
from ..detector_spec import DetectorSpec, build

_PATTERN_RE = re.compile(r"\bIIF\s*\(", re.IGNORECASE)

_DOC = """Detect T-SQL's IIF(). ora2pg -M copies the call through
unchanged -- notably, it does translate the sibling CHARINDEX in the
same statement, just wrongly (GAP-100) -- and PostgreSQL has no IIF,
so the routine loads cleanly and fails on its first call. See
docs/research/gap-098-mssql-iif.md."""

SPEC = DetectorSpec(
    name="mssql_iif",
    dialect="mssql",
    severity="high",
    pattern=_PATTERN_RE,
    snippet='IIF(...)',
)

find_mssql_iif = build(SPEC, mssql_lex)
find_mssql_iif.__doc__ = _DOC
