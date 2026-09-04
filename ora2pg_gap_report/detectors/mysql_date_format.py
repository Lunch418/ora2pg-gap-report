import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_DATE_FORMAT_RE = re.compile(r"\bDATE_FORMAT\s*\(", re.IGNORECASE)


def find_mysql_date_format(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's DATE_FORMAT(). ora2pg -m emits a bare
    parenthesised pair -- a row constructor -- with the to_char function
    name missing entirely and %d left untranslated, so nothing errors at
    any stage and the query silently returns a tuple instead of a
    formatted string. See docs/research/gap-081-mysql-date-format.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _DATE_FORMAT_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_date_format",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="DATE_FORMAT(...)",
                message_id="mysql_date_format",
            )
        )

    return findings
