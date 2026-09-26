import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name_index,
    inside_routine_body,
    line_at,
    mask_strings_and_comments,
    qualified_name_pattern,
)

# Not followed by IF NOT EXISTS: with that clause ora2pg keeps TEMPORARY
# and mangles the table instead, which is GAP-110's finding.
_TEMPORARY_TABLE_RE = re.compile(
    qualified_name_pattern(r"\bCREATE\s+TEMPORARY\s+TABLE(?!\s+IF\s+NOT\s+EXISTS\b)"),
    re.IGNORECASE,
)


def find_mysql_temporary_tables(source: str) -> list[Finding]:
    """Detect a top-level MySQL/MariaDB CREATE TEMPORARY TABLE. ora2pg -m
    drops TEMPORARY and generates a plain CREATE TABLE: the table loads,
    but it is now permanent and shared -- rows one session writes survive
    it and are visible to every other session, where MySQL gave each
    session its own copy that vanished with it. Nothing errors. See
    docs/research/gap-111-mysql-temporary-table.md.

    Inside a procedure, function or trigger the statement is copied into
    the PL/pgSQL body as written, where CREATE TEMPORARY TABLE means the
    same as in MySQL, so it is not flagged."""
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    return [
        Finding(
            detector="mysql_temporary_table",
            severity="high",
            object_name=m.group(1).upper(),
            line=line_at(clean, m.start()),
            snippet="CREATE TEMPORARY TABLE",
            message_id="mysql_temporary_table",
        )
        for m in _TEMPORARY_TABLE_RE.finditer(clean)
        if not inside_routine_body(index, m.start())
    ]
