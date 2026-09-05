import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

_APPLY_RE = re.compile(r"\b(CROSS|OUTER)\s+APPLY\b", re.IGNORECASE)

_DOC = """Detect Oracle's CROSS APPLY / OUTER APPLY. ora2pg passes it through
unchanged; PostgreSQL has no APPLY syntax at all -- the closest
equivalent is JOIN LATERAL / LEFT JOIN LATERAL, a manual rewrite.
See docs/research/gap-022-cross-apply.md."""

SPEC = DetectorSpec(
    name="cross_apply",
    dialect="oracle",
    severity="high",
    pattern=_APPLY_RE,
    snippet=lambda m: f"{m.group(1).upper()} APPLY",
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_apply_joins = build(SPEC, plsql_lex)
find_apply_joins.__doc__ = _DOC
