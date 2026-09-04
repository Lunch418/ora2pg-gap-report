import re

from ..models import Finding
from ..mysql_lex import (
    line_at,
    mask_strings_and_comments,
    qualified_name_pattern,
    table_column_definition_list,
)

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_FOREIGN_KEY_RE = re.compile(r"\bFOREIGN\s+KEY\b", re.IGNORECASE)


def find_mysql_foreign_keys(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB FOREIGN KEY clauses inside a CREATE TABLE
    column list. ora2pg -m drops them entirely -- no FOREIGN KEY appears
    anywhere in its output, and it has no separate foreign-key export
    type -- so referential integrity silently disappears with no error at
    any stage. See docs/research/gap-082-mysql-foreign-key.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        span = table_column_definition_list(clean, m.end())
        if span is None:
            continue  # bare CTAS with no column-definition list at all
        open_pos, close_pos = span
        column_list = clean[open_pos + 1 : close_pos]

        for fk_match in _FOREIGN_KEY_RE.finditer(column_list):
            findings.append(
                Finding(
                    detector="mysql_foreign_key",
                    severity="high",
                    object_name=m.group(1).upper(),
                    line=line_at(clean, open_pos + 1 + fk_match.start()),
                    snippet="FOREIGN KEY",
                    message_id="mysql_foreign_key",
                )
            )

    return findings
