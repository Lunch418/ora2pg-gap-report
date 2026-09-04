import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_PATTERN_RE = re.compile(r"\bCHARINDEX\s*\(", re.IGNORECASE)


def find_mssql_charindex(source: str) -> list[Finding]:
    """Detect T-SQL's CHARINDEX(). Unlike the other builtins in this
    batch ora2pg -M does translate it -- into position(...) -- but
    doubles the quotes around the search string, producing invalid SQL,
    so the routine loads cleanly and fails on its first call. See
    docs/research/gap-100-mssql-charindex.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_charindex",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="CHARINDEX(...)",
                message_id="mssql_charindex",
            )
        )

    return findings
