import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

_SQL_MACRO_RE = re.compile(r"\bSQL_MACRO\b", re.IGNORECASE)


def find_sql_macros(source: str) -> list[Finding]:
    """Detect Oracle's SQL_MACRO function modifier. ora2pg drops the
    keyword and converts the function into an ordinary PL/pgSQL function
    returning a string -- it compiles fine, but fails with a type error at
    any call site that uses it the way Oracle intended (inline SQL
    expression substitution, e.g. as a boolean expression directly in a
    WHERE clause). See docs/research/gap-019-sql-macro.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _SQL_MACRO_RE.finditer(visible):
        findings.append(
            Finding(
                detector="sql_macro",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="SQL_MACRO",
                message_id="sql_macro",
            )
        )

    return findings
