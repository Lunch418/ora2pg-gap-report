import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

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


def find_pivot_clauses(source: str) -> list[Finding]:
    """Detect Oracle's PIVOT/UNPIVOT clause. No PostgreSQL syntax
    equivalent exists — confirmed unconverted by ora2pg and invalid
    PostgreSQL SQL (see docs/research/gap-008-pivot-unpivot.md)."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PIVOT_RE.finditer(visible):
        findings.append(
            Finding(
                detector="pivot_clause",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=m.group(1).upper(),
                message_id="pivot_clause",
            )
        )

    return findings
