import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name_index,
    inside_routine_body,
    line_at,
    mask_strings_and_comments,
    qualified_name_pattern,
)

_IF_NOT_EXISTS_TABLE_RE = re.compile(
    qualified_name_pattern(r"\bCREATE\s+(?:TEMPORARY\s+)?TABLE\s+IF\s+NOT\s+EXISTS"),
    re.IGNORECASE,
)


def find_mysql_create_table_if_not_exists(source: str) -> list[Finding]:
    """Detect a top-level MySQL/MariaDB CREATE TABLE IF NOT EXISTS. ora2pg
    -m's table parser takes the word after TABLE as the table's name, so
    the table comes out as `CREATE TABLE if ( not EXISTS ...` with its real
    name and columns lost, and PostgreSQL rejects it with 'syntax error at
    or near "not"' -- stopping the whole schema load under the file's
    `\\set ON_ERROR_STOP ON`. The same table without IF NOT EXISTS
    converts. See docs/research/gap-110-mysql-create-table-if-not-exists.md.

    Inside a procedure, function or trigger the statement is copied into
    the PL/pgSQL body as written, and PostgreSQL has IF NOT EXISTS there,
    so it is not flagged."""
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    return [
        Finding(
            detector="mysql_create_table_if_not_exists",
            severity="high",
            object_name=m.group(1).upper(),
            line=line_at(clean, m.start()),
            snippet="CREATE TABLE IF NOT EXISTS",
            message_id="mysql_create_table_if_not_exists",
        )
        for m in _IF_NOT_EXISTS_TABLE_RE.finditer(clean)
        if not inside_routine_body(index, m.start())
    ]
