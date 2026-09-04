import re

from ..models import Finding
from ..mssql_lex import (
    line_at,
    mask_strings_and_comments,
    normalize_name,
    qualified_name_pattern,
    table_column_definition_list,
)

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_PATTERN_RE = re.compile(r"\b(?:NEWID|NEWSEQUENTIALID)\s*\(\s*\)", re.IGNORECASE)


def find_mssql_newid_defaults(source: str) -> list[Finding]:
    """Detect NEWID()/NEWSEQUENTIALID() column defaults. ora2pg -M
    maps them onto uuid_generate_v4() but never emits the CREATE
    EXTENSION "uuid-ossp" that function needs, so the generated CREATE
    TABLE fails to load. See docs/research/gap-088-mssql-newid-default.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        span = table_column_definition_list(clean, m.end())
        if span is None:
            continue  # CREATE TABLE ... AS SELECT, no column-definition list
        open_pos, close_pos = span
        column_list = clean[open_pos + 1 : close_pos]

        for col_match in _PATTERN_RE.finditer(column_list):
            findings.append(
                Finding(
                    detector="mssql_newid_default",
                    severity="high",
                    object_name=normalize_name(m.group(1)).upper(),
                    line=line_at(clean, open_pos + 1 + col_match.start()),
                    snippet=col_match.group(0).upper(),
                    message_id="mssql_newid_default",
                )
            )

    return findings
