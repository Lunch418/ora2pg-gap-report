import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_ON_DUP_RE = re.compile(r"\bON\s+DUPLICATE\s+KEY\s+UPDATE\b", re.IGNORECASE)


def find_mysql_on_duplicate_key_update(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's `INSERT ... ON DUPLICATE KEY UPDATE`
    upsert clause. ora2pg -m copies it through unchanged and PostgreSQL
    has no such INSERT syntax at all, so the containing procedure/
    function loads cleanly (bodies are not checked) and then fails on
    its first call. See docs/research/
    gap-070-mysql-on-duplicate-key-update.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _ON_DUP_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_on_duplicate_key_update",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="ON DUPLICATE KEY UPDATE",
                message_id="mysql_on_duplicate_key_update",
            )
        )

    return findings
