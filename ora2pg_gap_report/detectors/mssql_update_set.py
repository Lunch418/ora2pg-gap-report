import re

from .. import mssql_lex
from ..detector_spec import DetectorSpec, build

# `UPDATE <target> SET`, bounded and non-greedy so the match can never
# run past the end of its own statement into the next one's SET.
_PATTERN_RE = re.compile(r"\bUPDATE\s+[^;]{0,120}?\bSET\b", re.IGNORECASE)

_DOC = """Detect T-SQL UPDATE ... SET statements. ora2pg -M mistakes the
SET for T-SQL's variable-assignment SET, deletes the keyword and
turns the first assignment's `=` into `:=`, producing
`UPDATE t col := val` -- invalid in PL/pgSQL, so the routine loads
cleanly and fails on its first call. See docs/research/
gap-089-mssql-update-set.md."""

SPEC = DetectorSpec(
    name="mssql_update_set",
    dialect="mssql",
    severity="high",
    pattern=_PATTERN_RE,
    snippet='UPDATE ... SET',
)

find_mssql_update_set = build(SPEC, mssql_lex)
find_mssql_update_set.__doc__ = _DOC
