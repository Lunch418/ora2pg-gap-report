import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

# Anchored on the opening paren MATCH_RECOGNIZE always has -- a bare
# identifier called `match_recognize` (a legal Oracle column/table name)
# isn't the row-pattern-matching clause and must not be flagged.
_MATCH_RECOGNIZE_RE = re.compile(r"\bMATCH_RECOGNIZE\s*\(", re.IGNORECASE)

_DOC = """Detect Oracle's MATCH_RECOGNIZE row pattern matching clause.
ora2pg copies it into its output verbatim; PostgreSQL has no
equivalent at all, so the generated DDL fails to load with a syntax
error. See docs/research/gap-038-match-recognize.md."""

SPEC = DetectorSpec(
    name="match_recognize",
    dialect="oracle",
    severity="high",
    pattern=_MATCH_RECOGNIZE_RE,
    snippet='MATCH_RECOGNIZE',
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_match_recognize = build(SPEC, plsql_lex)
find_match_recognize.__doc__ = _DOC
