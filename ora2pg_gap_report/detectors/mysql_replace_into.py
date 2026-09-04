import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

# `INTO` is required by the match so the ordinary REPLACE(str, from, to)
# string function -- an entirely different thing, and one ora2pg handles
# fine -- can't produce a finding.
_REPLACE_INTO_RE = re.compile(r"\bREPLACE\s+INTO\b", re.IGNORECASE)


def find_mysql_replace_into(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's REPLACE INTO statement. ora2pg -m copies it
    through unchanged and PostgreSQL has no such statement, so the
    containing routine loads cleanly and fails on its first call. Note
    that ON CONFLICT DO UPDATE is not an exact equivalent -- REPLACE
    deletes and re-inserts, which fires delete-side triggers/cascades.
    See docs/research/gap-076-mysql-replace-into.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _REPLACE_INTO_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_replace_into",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="REPLACE INTO",
                message_id="mysql_replace_into",
            )
        )

    return findings
