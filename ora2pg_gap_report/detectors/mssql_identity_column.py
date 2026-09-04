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
# \b after IDENTITY (not just before) so a column name that merely starts
# with the word -- IDENTITY_FLAG, say -- doesn't match: the original
# pattern had no right-side boundary, so "IDENTITY_FLAG bit" matched
# "IDENTITY" as if the column itself had the property.
_PATTERN_RE = re.compile(r"\bIDENTITY\b\s*(?:\(\s*\d+\s*,\s*\d+\s*\))?", re.IGNORECASE)


def find_mssql_identity_columns(source: str) -> list[Finding]:
    """Detect T-SQL IDENTITY columns. ora2pg -M drops the property
    entirely -- the column becomes a plain integer with no serial, no
    GENERATED clause and no sequence anywhere in the output -- so an
    INSERT that relied on the server supplying the key fails on the NOT
    NULL constraint. See docs/research/gap-090-mssql-identity-column.md."""
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
                    detector="mssql_identity_column",
                    severity="high",
                    object_name=normalize_name(m.group(1)).upper(),
                    line=line_at(clean, open_pos + 1 + col_match.start()),
                    snippet="IDENTITY",
                    message_id="mssql_identity_column",
                )
            )

    return findings
