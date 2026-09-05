import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

# 'AS OF TIMESTAMP'/'AS OF SCN' -- Oracle flashback query, reading a table
# as it existed at a past point in time. No other meaning for this exact
# phrase in Oracle SQL.
_FLASHBACK_RE = re.compile(r"\bAS\s+OF\s+(TIMESTAMP|SCN)\b", re.IGNORECASE)

_DOC = """Detect Oracle's flashback query (AS OF TIMESTAMP/SCN). No
PostgreSQL equivalent exists at all -- see
docs/research/gap-011-flashback-query.md."""

SPEC = DetectorSpec(
    name="flashback_query",
    dialect="oracle",
    severity="high",
    pattern=_FLASHBACK_RE,
    snippet=lambda m: re.sub(r"\s+", " ", m.group(0)),
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_flashback_queries = build(SPEC, plsql_lex)
find_flashback_queries.__doc__ = _DOC
