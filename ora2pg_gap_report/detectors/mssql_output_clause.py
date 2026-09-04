import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_PATTERN_RE = re.compile(r"\bOUTPUT\s+(?:INSERTED|DELETED)\.", re.IGNORECASE)


def find_mssql_output_clause(source: str) -> list[Finding]:
    """Detect T-SQL's OUTPUT INSERTED/DELETED clause. ora2pg -M copies
    it through unchanged; PostgreSQL spells the same idea as RETURNING,
    so the containing routine loads cleanly and fails on its first call.
    See docs/research/gap-097-mssql-output-clause.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_output_clause",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=m.group(0).upper(),
                message_id="mssql_output_clause",
            )
        )

    return findings
