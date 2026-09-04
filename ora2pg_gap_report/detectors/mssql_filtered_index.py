import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

# A filtered index is a CREATE INDEX carrying a WHERE clause; the
# bounded non-greedy body keeps the match inside one statement.
_PATTERN_RE = re.compile(r"\bCREATE\s+(?:UNIQUE\s+)?(?:CLUSTERED\s+|NONCLUSTERED\s+)?INDEX\b[^;]{0,300}?\bWHERE\b", re.IGNORECASE)


def find_mssql_filtered_indexes(source: str) -> list[Finding]:
    """Detect T-SQL filtered indexes (`CREATE INDEX ... WHERE ...`).
    ora2pg -M drops the whole statement, emitting no index at all, even
    though PostgreSQL supports partial indexes with the same syntax. See
    docs/research/gap-101-mssql-filtered-index.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_filtered_index",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="filtered INDEX",
                message_id="mssql_filtered_index",
            )
        )

    return findings
