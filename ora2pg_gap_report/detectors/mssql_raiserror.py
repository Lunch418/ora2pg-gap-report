import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_PATTERN_RE = re.compile(r"\b(RAISERROR|THROW)\b", re.IGNORECASE)


def find_mssql_raiserror(source: str) -> list[Finding]:
    """Detect T-SQL RAISERROR and THROW. ora2pg -M copies both through
    unchanged; PL/pgSQL has neither, so the containing routine loads
    cleanly and fails on its first call. See docs/research/
    gap-093-mssql-raiserror.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_raiserror",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=m.group(1).upper(),
                message_id="mssql_raiserror",
            )
        )

    return findings
