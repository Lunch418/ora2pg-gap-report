import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_INSERT_IGNORE_RE = re.compile(r"\bINSERT\s+IGNORE\b", re.IGNORECASE)


def find_mysql_insert_ignore(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's INSERT IGNORE. ora2pg -m copies it through
    unchanged; PostgreSQL has no such INSERT syntax, so the containing
    routine loads cleanly and fails on its first call. ON CONFLICT DO
    NOTHING is narrower than IGNORE, not an exact equivalent. See
    docs/research/gap-077-mysql-insert-ignore.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _INSERT_IGNORE_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_insert_ignore",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="INSERT IGNORE",
                message_id="mysql_insert_ignore",
            )
        )

    return findings
