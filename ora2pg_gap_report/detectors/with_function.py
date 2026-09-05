import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

# Oracle 12c+ inline function/procedure definition inside a query's own
# WITH clause. "WITH FUNCTION"/"WITH PROCEDURE" has no other meaning in
# Oracle SQL (the ordinary CTE form is always 'WITH name AS (...)').
_WITH_FUNCTION_RE = re.compile(r"\bWITH\s+(FUNCTION|PROCEDURE)\b", re.IGNORECASE)

_DOC = """Detect Oracle's inline WITH FUNCTION/PROCEDURE clause. Confirmed to
cause a genuine parser corruption in ora2pg, not just an unconverted
pass-through -- see docs/research/gap-010-with-function.md."""

SPEC = DetectorSpec(
    name="with_function",
    dialect="oracle",
    severity="high",
    pattern=_WITH_FUNCTION_RE,
    snippet=lambda m: re.sub(r"\s+", " ", m.group(0)),
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_with_function_clauses = build(SPEC, plsql_lex)
find_with_function_clauses.__doc__ = _DOC
