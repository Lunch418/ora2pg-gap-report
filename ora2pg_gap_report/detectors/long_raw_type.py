import re

from ..models import Finding
from ..plsql_lex import (
    line_at,
    mask_strings_and_comments,
    qualified_name_pattern,
    table_column_definition_list,
)

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# LONG RAW specifically -- plain LONG is Oracle's legacy *character* type
# and `LONG:text` is both ora2pg's documented mapping and the right one,
# so it must not be flagged. Only the binary variant is converted against
# ora2pg's own documented default.
_LONG_RAW_RE = re.compile(r"\bLONG\s+RAW\b", re.IGNORECASE)


def find_long_raw_columns(source: str) -> list[Finding]:
    """Detect Oracle LONG RAW columns. ora2pg maps them to `text` even
    though its own documented default is `LONG RAW:bytea`, so binary
    content cannot be loaded into the generated column. See
    docs/research/gap-050-long-raw-type.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        span = table_column_definition_list(clean, m.end())
        if span is None:
            continue  # bare CTAS with no column-definition list at all
        open_pos, close_pos = span
        column_list = clean[open_pos + 1 : close_pos]

        for col_match in _LONG_RAW_RE.finditer(column_list):
            findings.append(
                Finding(
                    detector="long_raw_type",
                    severity="high",
                    object_name=m.group(1).upper(),
                    line=line_at(clean, open_pos + 1 + col_match.start()),
                    snippet="LONG RAW",
                    message_id="long_raw_type",
                )
            )

    return findings
