import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_LAST_INSERT_ID_RE = re.compile(r"\bLAST_INSERT_ID\s*\(", re.IGNORECASE)


def find_mysql_last_insert_id(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's LAST_INSERT_ID() function. ora2pg -m copies
    the call through unchanged and PostgreSQL has no such function, so
    the containing routine loads cleanly and fails on its first call.
    See docs/research/gap-079-mysql-last-insert-id.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _LAST_INSERT_ID_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_last_insert_id",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="LAST_INSERT_ID()",
                message_id="mysql_last_insert_id",
            )
        )

    return findings
