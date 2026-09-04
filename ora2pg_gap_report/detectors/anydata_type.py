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
# ANYDATA / ANYDATASET / ANYTYPE, with or without the SYS. prefix -- all
# three are the same self-describing-container family and ora2pg treats
# them the same way (it passes the type name straight through).
_ANYDATA_RE = re.compile(
    r"\b(?:SYS\s*\.\s*)?(ANYDATASET|ANYDATA|ANYTYPE)\b",
    re.IGNORECASE,
)


def find_anydata_columns(source: str) -> list[Finding]:
    """Detect Oracle ANYDATA/ANYDATASET/ANYTYPE columns. ora2pg copies
    the type name through unchanged and PostgreSQL has neither the type
    nor the SYS schema, so the generated DDL fails to load. See
    docs/research/gap-051-anydata-type.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        span = table_column_definition_list(clean, m.end())
        if span is None:
            continue  # bare CTAS with no column-definition list at all
        open_pos, close_pos = span
        column_list = clean[open_pos + 1 : close_pos]

        for col_match in _ANYDATA_RE.finditer(column_list):
            findings.append(
                Finding(
                    detector="anydata_type",
                    severity="high",
                    object_name=m.group(1).upper(),
                    line=line_at(clean, open_pos + 1 + col_match.start()),
                    snippet=col_match.group(1).upper(),
                    message_id="anydata_type",
                )
            )

    return findings
