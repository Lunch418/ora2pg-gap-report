import re

from .. import mssql_lex
from ..detector_spec import DetectorSpec, build

_PATTERN_RE = re.compile(r"\bCHARINDEX\s*\(", re.IGNORECASE)

_DOC = """Detect T-SQL's CHARINDEX(). Unlike the other builtins in this
batch ora2pg -M does translate it -- into position(...) -- but
doubles the quotes around the search string, producing invalid SQL,
so the routine loads cleanly and fails on its first call. See
docs/research/gap-100-mssql-charindex.md."""

SPEC = DetectorSpec(
    name="mssql_charindex",
    dialect="mssql",
    severity="high",
    pattern=_PATTERN_RE,
    snippet='CHARINDEX(...)',
)

find_mssql_charindex = build(SPEC, mssql_lex)
find_mssql_charindex.__doc__ = _DOC
