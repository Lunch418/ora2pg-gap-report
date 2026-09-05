import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

# Both spellings of Oracle's null-treatment clause on analytic functions.
# RESPECT NULLS is Oracle's default and therefore usually implicit, but it
# is legal to write it out, and when it is written out ora2pg copies it
# through exactly like IGNORE NULLS -- confirmed by a separate probe, so
# both are flagged rather than just the interesting one.
_NULL_TREATMENT_RE = re.compile(r"\b(?:IGNORE|RESPECT)\s+NULLS\b", re.IGNORECASE)

_DOC = """Detect Oracle's IGNORE NULLS / RESPECT NULLS clause on analytic
functions. ora2pg passes it through unchanged and PostgreSQL 16 has
no equivalent syntax, so the generated query fails to parse. See
docs/research/gap-048-ignore-nulls.md."""

SPEC = DetectorSpec(
    name="ignore_nulls",
    dialect="oracle",
    severity="high",
    pattern=_NULL_TREATMENT_RE,
    snippet=lambda m: " ".join(m.group(0).upper().split()),
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_ignore_nulls = build(SPEC, plsql_lex)
find_ignore_nulls.__doc__ = _DOC
