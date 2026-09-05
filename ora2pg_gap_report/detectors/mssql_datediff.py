import re

from .. import mssql_lex
from ..detector_spec import DetectorSpec, build

_PATTERN_RE = re.compile(r"\bDATEDIFF\s*\(", re.IGNORECASE)

_DOC = """Detect T-SQL's DATEDIFF(). ora2pg -M copies it through
unchanged, even though it does convert DATEADD and DATEPART in the
same statement, so the routine loads cleanly and fails on its first
call. See docs/research/gap-099-mssql-datediff.md."""

SPEC = DetectorSpec(
    name="mssql_datediff",
    dialect="mssql",
    severity="high",
    pattern=_PATTERN_RE,
    snippet='DATEDIFF(...)',
)

find_mssql_datediff = build(SPEC, mssql_lex)
find_mssql_datediff.__doc__ = _DOC
