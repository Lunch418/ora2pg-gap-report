import re

from ..models import Finding
from ..plsql_lex import enclosing_object_name, enclosing_object_name_index, line_at, mask_strings_and_comments

_SQL_MACRO_RE = re.compile(r"\bSQL_MACRO\b", re.IGNORECASE)

_MESSAGE = (
    "SQL_MACRO — функция-макрос Oracle (SQL_MACRO(SCALAR) или "
    "SQL_MACRO(TABLE), доступно с Oracle 20c), задуманная как текстовая "
    "подстановка прямо в SQL (в WHERE/FROM), а не как обычный вызов "
    "функции. ora2pg молча отбрасывает ключевое слово SQL_MACRO и "
    "конвертирует тело в обычную PL/pgSQL функцию, возвращающую строку "
    "(подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-019-sql-macro.md). Сама функция компилируется без "
    "ошибок, но при вызове в том виде, для которого она была написана "
    "(например, прямо в WHERE как булево выражение), падает с ошибкой "
    "типа — PostgreSQL пытается использовать текстовый результат функции "
    "как boolean напрямую, а не подставить его текст в запрос как "
    "делал Oracle. Нужно вручную переписать вызывающий код, встроив "
    "логику макроса как обычное условие или подзапрос."
)


def find_sql_macros(source: str) -> list[Finding]:
    """Detect Oracle's SQL_MACRO function modifier. ora2pg drops the
    keyword and converts the function into an ordinary PL/pgSQL function
    returning a string -- it compiles fine, but fails with a type error at
    any call site that uses it the way Oracle intended (inline SQL
    expression substitution, e.g. as a boolean expression directly in a
    WHERE clause). See docs/research/gap-019-sql-macro.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _SQL_MACRO_RE.finditer(clean):
        findings.append(
            Finding(
                detector="sql_macro",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="SQL_MACRO",
                message=_MESSAGE,
            )
        )

    return findings
