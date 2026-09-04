import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_PATTERN_RE = re.compile(r"\bIIF\s*\(", re.IGNORECASE)


def find_mssql_iif(source: str) -> list[Finding]:
    """Detect T-SQL's IIF(). ora2pg -M copies the call through
    unchanged -- notably, it does translate the sibling CHARINDEX in the
    same statement, just wrongly (GAP-100) -- and PostgreSQL has no IIF,
    so the routine loads cleanly and fails on its first call. See
    docs/research/gap-098-mssql-iif.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_iif",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="IIF(...)",
                message_id="mssql_iif",
            )
        )

    return findings
