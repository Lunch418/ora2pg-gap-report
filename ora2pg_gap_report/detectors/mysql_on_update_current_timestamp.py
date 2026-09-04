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
_ON_UPDATE_RE = re.compile(r"\bON\s+UPDATE\s+CURRENT_TIMESTAMP\b", re.IGNORECASE)


def find_mysql_on_update_current_timestamp(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's `DEFAULT CURRENT_TIMESTAMP ON UPDATE
    CURRENT_TIMESTAMP` column clause. ora2pg -m copies the `ON UPDATE
    CURRENT_TIMESTAMP` fragment verbatim into the generated DEFAULT,
    which is not valid PostgreSQL syntax at all -- CREATE TABLE fails to
    load immediately. See docs/research/
    gap-069-mysql-on-update-current-timestamp.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        span = table_column_definition_list(clean, m.end())
        if span is None:
            continue  # bare CTAS with no column-definition list at all
        open_pos, close_pos = span
        column_list = clean[open_pos + 1 : close_pos]

        for col_match in _ON_UPDATE_RE.finditer(column_list):
            findings.append(
                Finding(
                    detector="mysql_on_update_current_timestamp",
                    severity="high",
                    object_name=m.group(1).upper(),
                    line=line_at(clean, open_pos + 1 + col_match.start()),
                    snippet="ON UPDATE CURRENT_TIMESTAMP",
                    message_id="mysql_on_update_current_timestamp",
                )
            )

    return findings
