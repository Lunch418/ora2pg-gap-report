import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

# NLSSORT(...) and NLS_SORT are two different things with confusingly
# similar names: NLSSORT() is the function that produces a collation key
# (the one ora2pg rewrites into a COLLATE clause), NLS_SORT is a session
# parameter name that usually appears *inside* NLSSORT's second argument
# ('NLS_SORT=GERMAN'). Only the function call is matched here -- the
# parameter name lives inside a string literal, which is masked out
# before this pattern ever runs.
_NLSSORT_RE = re.compile(r"\bNLSSORT\s*\(", re.IGNORECASE)

_DOC = """Detect Oracle's NLSSORT() collation function. ora2pg rewrites it
into a COLLATE clause but carries the Oracle language name straight
across, and PostgreSQL has no collation under that name, so the
generated query fails to run. See docs/research/gap-049-nlssort.md."""

SPEC = DetectorSpec(
    name="nlssort",
    dialect="oracle",
    severity="high",
    pattern=_NLSSORT_RE,
    snippet='NLSSORT(',
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_nlssort = build(SPEC, plsql_lex)
find_nlssort.__doc__ = _DOC
