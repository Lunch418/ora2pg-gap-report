import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

_JSON_TABLE_RE = re.compile(r"\bJSON_TABLE\s*\(", re.IGNORECASE)


def find_json_table_calls(source: str) -> list[Finding]:
    """Detect Oracle's JSON_TABLE(...) SQL/JSON function. ora2pg passes it
    through unchanged; PostgreSQL 16 and earlier have no such function at
    all (PostgreSQL 17 added JSON_TABLE, but with a COLUMNS syntax not
    verified here to match Oracle's own). See
    docs/research/gap-017-json-table.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _JSON_TABLE_RE.finditer(visible):
        findings.append(
            Finding(
                detector="json_table",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="JSON_TABLE(...)",
                message_id="json_table",
            )
        )

    return findings
