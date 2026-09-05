import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

# PIVOT/UNPIVOT always take a parenthesized spec ('PIVOT (aggregate FOR
# column IN (...))'), optionally preceded by their own modifier keywords
# ('PIVOT XML (...)' for a dynamic/unknown IN-list; 'UNPIVOT INCLUDE
# NULLS (...)'/'UNPIVOT EXCLUDE NULLS (...)') -- requiring the eventual
# '(' (not immediately, to allow those modifiers) rules out a bare
# "pivot"/"unpivot" used as an ordinary identifier not followed by a
# call/subclause at all.
_PIVOT_RE = re.compile(
    r"\b(PIVOT|UNPIVOT)\b\s*(?:XML\s+|(?:INCLUDE|EXCLUDE)\s+NULLS\s+)?\(",
    re.IGNORECASE,
)

_DOC = """Detect Oracle's PIVOT/UNPIVOT clause. No PostgreSQL syntax
equivalent exists — confirmed unconverted by ora2pg and invalid
PostgreSQL SQL (see docs/research/gap-008-pivot-unpivot.md)."""

SPEC = DetectorSpec(
    name="pivot_clause",
    dialect="oracle",
    severity="high",
    pattern=_PIVOT_RE,
    snippet=lambda m: m.group(1).upper(),
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_pivot_clauses = build(SPEC, plsql_lex)
find_pivot_clauses.__doc__ = _DOC
