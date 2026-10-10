import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    skip_balanced_parens,
)

_JSON_TABLE_RE = re.compile(r"\bJSON_TABLE\s*\(", re.IGNORECASE)
_COLUMNS_RE = re.compile(r"\bCOLUMNS\b", re.IGNORECASE)
# Oracle writes the error/empty handling before COLUMNS; PostgreSQL 17+
# takes it only after the column list.
_ON_ERROR_BEFORE_COLUMNS_RE = re.compile(r"\bON\s+(?:ERROR|EMPTY)\b", re.IGNORECASE)


def find_json_table_calls(source: str) -> list[Finding]:
    """Detect Oracle's JSON_TABLE(...) SQL/JSON function. ora2pg passes it
    through unchanged. PostgreSQL 16 and earlier have no such function at
    all; PostgreSQL 17 added it, and ora2pg's output then loads and returns
    the same rows -- NESTED PATH included -- except where Oracle's error
    or empty handling stands before COLUMNS (`'$[*]' ERROR ON ERROR
    COLUMNS (...)`), which PostgreSQL 17 and 18 reject: those calls get the
    message `json_table.on_error`, which --pg-version 17 still reports.
    Checked with ora2pg 25.0 on PostgreSQL 16, 17 and 18. See
    docs/research/gap-017-json-table.md."""
    searched = mask_dynamic_sql_visible(source)
    if "JSON_TABLE" not in searched.upper():
        return []
    index = enclosing_object_name_index(searched)
    findings: list[Finding] = []

    def found(m: re.Match[str], message_id: str) -> Finding:
        return Finding(
            detector="json_table",
            severity="high",
            object_name=enclosing_object_name(index, m.start()),
            line=line_at(searched, m.start()),
            snippet="JSON_TABLE(...)",
            message_id=message_id,
        )

    for m in _JSON_TABLE_RE.finditer(searched):
        close = skip_balanced_parens(searched, m.end() - 1)
        columns = _COLUMNS_RE.search(searched, m.end(), close)
        head = searched[m.end() : columns.start() if columns else close]
        if _ON_ERROR_BEFORE_COLUMNS_RE.search(head):
            findings.append(found(m, message_id="json_table.on_error"))
        else:
            findings.append(found(m, message_id="json_table"))
    return findings
