import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_PATTERN_RE = re.compile(r"\bDATEDIFF\s*\(", re.IGNORECASE)


def find_mssql_datediff(source: str) -> list[Finding]:
    """Detect T-SQL's DATEDIFF(). ora2pg -M copies it through
    unchanged, even though it does convert DATEADD and DATEPART in the
    same statement, so the routine loads cleanly and fails on its first
    call. See docs/research/gap-099-mssql-datediff.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_datediff",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="DATEDIFF(...)",
                message_id="mssql_datediff",
            )
        )

    return findings
