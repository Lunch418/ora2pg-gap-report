import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

# 'AS OF TIMESTAMP'/'AS OF SCN' -- Oracle flashback query, reading a table
# as it existed at a past point in time. No other meaning for this exact
# phrase in Oracle SQL.
_FLASHBACK_RE = re.compile(r"\bAS\s+OF\s+(TIMESTAMP|SCN)\b", re.IGNORECASE)


def find_flashback_queries(source: str) -> list[Finding]:
    """Detect Oracle's flashback query (AS OF TIMESTAMP/SCN). No
    PostgreSQL equivalent exists at all -- see
    docs/research/gap-011-flashback-query.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _FLASHBACK_RE.finditer(visible):
        findings.append(
            Finding(
                detector="flashback_query",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=re.sub(r"\s+", " ", m.group(0)),
                message_id="flashback_query",
            )
        )

    return findings
