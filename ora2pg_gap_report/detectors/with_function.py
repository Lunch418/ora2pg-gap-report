import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

# Oracle 12c+ inline function/procedure definition inside a query's own
# WITH clause. "WITH FUNCTION"/"WITH PROCEDURE" has no other meaning in
# Oracle SQL (the ordinary CTE form is always 'WITH name AS (...)').
_WITH_FUNCTION_RE = re.compile(r"\bWITH\s+(FUNCTION|PROCEDURE)\b", re.IGNORECASE)


def find_with_function_clauses(source: str) -> list[Finding]:
    """Detect Oracle's inline WITH FUNCTION/PROCEDURE clause. Confirmed to
    cause a genuine parser corruption in ora2pg, not just an unconverted
    pass-through -- see docs/research/gap-010-with-function.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _WITH_FUNCTION_RE.finditer(visible):
        findings.append(
            Finding(
                detector="with_function",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=re.sub(r"\s+", " ", m.group(0)),
                message_id="with_function",
            )
        )

    return findings
