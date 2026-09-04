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
_SET_RE = re.compile(r"\bSET\s*\(", re.IGNORECASE)


def find_mysql_set_columns(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB SET(...) multi-value columns. ora2pg -m maps
    them onto plain text, which loads and works but validates nothing --
    any string at all becomes storable afterwards. See docs/research/
    gap-086-mysql-set-type.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        span = table_column_definition_list(clean, m.end())
        if span is None:
            continue  # bare CTAS with no column-definition list at all
        open_pos, close_pos = span
        column_list = clean[open_pos + 1 : close_pos]

        for col_match in _SET_RE.finditer(column_list):
            findings.append(
                Finding(
                    detector="mysql_set_type",
                    severity="medium",
                    object_name=m.group(1).upper(),
                    line=line_at(clean, open_pos + 1 + col_match.start()),
                    snippet="SET(...)",
                    message_id="mysql_set_type",
                )
            )

    return findings
