import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

# Anchored on the full `SAMPLE [BLOCK] (<number>)` shape rather than the
# bare word: `sample` is an entirely ordinary identifier (a column, a
# table, a variable named `sample` is common), and only the row-sampling
# clause -- the keyword immediately followed by a parenthesised percentage
# -- is the construct that fails to convert.
_SAMPLE_RE = re.compile(
    r"\bSAMPLE\s*(?:BLOCK\s*)?\(\s*\d+(?:\.\d+)?\s*\)",
    re.IGNORECASE,
)

_DOC = """Detect Oracle's SAMPLE (n) / SAMPLE BLOCK (n) row-sampling clause.
ora2pg passes it through unchanged; PostgreSQL spells the same idea
TABLESAMPLE with different syntax, so the generated code fails to
load. See docs/research/gap-042-sample-clause.md."""

SPEC = DetectorSpec(
    name="sample_clause",
    dialect="oracle",
    severity="high",
    pattern=_SAMPLE_RE,
    snippet=lambda m: " ".join(m.group(0).upper().split()),
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_sample_clauses = build(SPEC, plsql_lex)
find_sample_clauses.__doc__ = _DOC
