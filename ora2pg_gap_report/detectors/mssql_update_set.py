import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

# `UPDATE <target> SET`, bounded and non-greedy so the match can never
# run past the end of its own statement into the next one's SET.
_PATTERN_RE = re.compile(r"\bUPDATE\s+[^;]{0,120}?\bSET\b", re.IGNORECASE)


def find_mssql_update_set(source: str) -> list[Finding]:
    """Detect T-SQL UPDATE ... SET statements. ora2pg -M mistakes the
    SET for T-SQL's variable-assignment SET, deletes the keyword and
    turns the first assignment's `=` into `:=`, producing
    `UPDATE t col := val` -- invalid in PL/pgSQL, so the routine loads
    cleanly and fails on its first call. See docs/research/
    gap-089-mssql-update-set.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_update_set",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="UPDATE ... SET",
                message_id="mssql_update_set",
            )
        )

    return findings
