import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_PATTERN_RE = re.compile(r"\bTOP\s*\(?\s*(?:\d+|@\w+)", re.IGNORECASE)


def find_mssql_top_clause(source: str) -> list[Finding]:
    """Detect T-SQL's TOP n clause. ora2pg -M copies it through
    unchanged and PostgreSQL has no TOP at all, so the containing routine
    loads cleanly and fails on its first call. See docs/research/
    gap-095-mssql-top-clause.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_top_clause",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="TOP n",
                message_id="mssql_top_clause",
            )
        )

    return findings
