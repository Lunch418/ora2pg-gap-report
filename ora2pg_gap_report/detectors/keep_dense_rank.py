import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

# Anchored on the whole KEEP (DENSE_RANK ...) shape, not a bare KEEP: the
# word on its own is a legal identifier and appears in unrelated Oracle
# code (a column named `keep`, `DBMS_*.KEEP` calls). Only the aggregate's
# own syntax -- KEEP immediately followed by a paren and DENSE_RANK -- is
# the construct that doesn't survive conversion.
_KEEP_RE = re.compile(r"\bKEEP\s*\(\s*DENSE_RANK\b", re.IGNORECASE)

_DOC = """Detect Oracle's KEEP (DENSE_RANK FIRST|LAST ORDER BY ...)
aggregate modifier. ora2pg passes it through unchanged and PostgreSQL
has no KEEP syntax, so the generated code fails to load. See
docs/research/gap-040-keep-dense-rank.md."""

SPEC = DetectorSpec(
    name="keep_dense_rank",
    dialect="oracle",
    severity="high",
    pattern=_KEEP_RE,
    snippet='KEEP (DENSE_RANK ...)',
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_keep_dense_rank = build(SPEC, plsql_lex)
find_keep_dense_rank.__doc__ = _DOC
