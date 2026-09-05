import re

from .. import mssql_lex
from ..detector_spec import DetectorSpec, build

_PATTERN_RE = re.compile(r"\bBEGIN\s+TRY\b", re.IGNORECASE)

_DOC = """Detect T-SQL BEGIN TRY/BEGIN CATCH blocks. ora2pg -M copies the
whole construct through unchanged; PL/pgSQL spells error handling as
BEGIN ... EXCEPTION WHEN ... END, so the routine loads cleanly and
fails on its first call. See docs/research/gap-094-mssql-try-catch.md."""

SPEC = DetectorSpec(
    name="mssql_try_catch",
    dialect="mssql",
    severity="high",
    pattern=_PATTERN_RE,
    snippet='BEGIN TRY',
)

find_mssql_try_catch = build(SPEC, mssql_lex)
find_mssql_try_catch.__doc__ = _DOC
