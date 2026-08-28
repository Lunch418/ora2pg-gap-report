import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

# A cursor *expression* -- CURSOR( immediately followed by a SELECT -- not
# a cursor *declaration* ('CURSOR c IS SELECT ...', which is an ordinary
# PL/SQL declaration ora2pg converts correctly and which must not be
# flagged here). The parenthesis directly after the keyword is what
# separates the two: a declaration always has an identifier there.
_CURSOR_EXPRESSION_RE = re.compile(r"\bCURSOR\s*\(\s*(?:\(\s*)*SELECT\b", re.IGNORECASE)

_MESSAGE = (
    "CURSOR(SELECT ...) — курсорное выражение Oracle: вложенный запрос, "
    "возвращаемый как отдельный столбец-курсор, который клиент потом "
    "открывает и читает построчно. ora2pg копирует конструкцию в вывод как "
    "есть (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-055-cursor-expression.md). В PostgreSQL курсорных "
    "выражений нет, и запрос падает синтаксической ошибкой на SELECT внутри "
    "CURSOR(. Переписывается либо на обычное соединение с агрегацией "
    "дочерних строк в массив/json (array_agg, json_agg) — чаще всего "
    "именно это и имелось в виду, — либо на отдельную функцию, "
    "возвращающую refcursor, если клиент действительно читает вложенный "
    "набор построчно."
)


def find_cursor_expressions(source: str) -> list[Finding]:
    """Detect Oracle's CURSOR(SELECT ...) cursor expression. ora2pg
    copies it through unchanged and PostgreSQL has no equivalent, so the
    generated query fails to parse. Deliberately does not match ordinary
    'CURSOR c IS SELECT ...' declarations. See
    docs/research/gap-055-cursor-expression.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _CURSOR_EXPRESSION_RE.finditer(visible):
        findings.append(
            Finding(
                detector="cursor_expression",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="CURSOR(SELECT",
                message=_MESSAGE,
            )
        )

    return findings
