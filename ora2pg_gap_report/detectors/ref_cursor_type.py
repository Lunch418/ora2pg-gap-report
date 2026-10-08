import re

from ..models import Finding
from ..plsql_lex import (
    IDENTIFIER,
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_REF_CURSOR_TYPE_RE = re.compile(
    rf"\bTYPE\s+({IDENTIFIER})\s+IS\s+REF\s+CURSOR\b",
    re.IGNORECASE,
)


def find_ref_cursor_type(source: str) -> list[Finding]:
    """Detect `TYPE name IS REF CURSOR [RETURN ...]`, a cursor-variable type
    declared in a package or a routine.

    ora2pg turns it into `CREATE OR REPLACE TYPE pkg.name AS REFCURSOR`,
    which is not PostgreSQL at all: there is no CREATE OR REPLACE TYPE, and
    refcursor is a single built-in type with no named variants. The
    statement fails to load ('syntax error at or near "TYPE"'), and so does
    every function declared to return the type ('type "name" does not
    exist'). In Oracle 23ai the package compiles and the cursor is read
    normally. The fix is to use refcursor itself wherever the type is
    named. Reproduced with ora2pg 25.0 from a hand-written package and from
    DBMS_METADATA.GET_DDL. See docs/research/gap-115-ref-cursor-type.md.

    SYS_REFCURSOR is not this gap: it is a built-in name ora2pg maps to
    refcursor correctly."""
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    findings: list[Finding] = []
    for m in _REF_CURSOR_TYPE_RE.finditer(clean):
        findings.append(
            Finding(
                detector="ref_cursor_type",
                severity="high",
                object_name=f"{enclosing_object_name(index, m.start())}.{m.group(1).upper()}",
                line=line_at(clean, m.start()),
                snippet=f"TYPE {m.group(1)} IS REF CURSOR",
                message_id="ref_cursor_type",
            )
        )
    return findings
