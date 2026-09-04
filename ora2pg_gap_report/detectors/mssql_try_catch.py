import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_PATTERN_RE = re.compile(r"\bBEGIN\s+TRY\b", re.IGNORECASE)


def find_mssql_try_catch(source: str) -> list[Finding]:
    """Detect T-SQL BEGIN TRY/BEGIN CATCH blocks. ora2pg -M copies the
    whole construct through unchanged; PL/pgSQL spells error handling as
    BEGIN ... EXCEPTION WHEN ... END, so the routine loads cleanly and
    fails on its first call. See docs/research/gap-094-mssql-try-catch.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_try_catch",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="BEGIN TRY",
                message_id="mssql_try_catch",
            )
        )

    return findings
