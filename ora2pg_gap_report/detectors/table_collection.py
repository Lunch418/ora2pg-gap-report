import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

# The TABLE(...) collection-unnesting operator, which only ever appears in
# a FROM clause (or after a join keyword). Anchoring on the preceding
# FROM/JOIN keyword is what keeps `CREATE TABLE (`, `ALTER TABLE ... (`,
# `TRUNCATE TABLE ...`, `TYPE t IS TABLE OF ...` and every other ordinary
# use of the word TABLE out of the results -- the bare word is far too
# common in SQL to match on its own.
_TABLE_OPERATOR_RE = re.compile(
    r"\b(?:FROM|JOIN|CROSS\s+APPLY|OUTER\s+APPLY)\s*,?\s*(?:THE\s+)?TABLE\s*\(",
    re.IGNORECASE,
)

_MESSAGE = (
    "TABLE(...) — оператор Oracle, разворачивающий коллекцию (nested "
    "table, VARRAY или результат pipelined-функции) в набор строк прямо во "
    "FROM. ora2pg копирует его в вывод как есть (подтверждено реальным "
    "прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-054-table-collection.md). В PostgreSQL такого "
    "оператора нет, и запрос падает синтаксической ошибкой прямо на слове "
    "TABLE. Ближайший аналог — unnest(...) для массива или обычный вызов "
    "set-returning функции во FROM (FROM get_ids(42)), но подстановка не "
    "механическая: она зависит от того, чем в PostgreSQL стала сама "
    "коллекция (массивом, отдельной таблицей или функцией, возвращающей "
    "SETOF), — см. GAP-021/collection_type.py про сами объявления таких "
    "типов."
)


def find_table_collection_operator(source: str) -> list[Finding]:
    """Detect Oracle's TABLE(...) collection-unnesting operator in a FROM
    clause. ora2pg copies it through unchanged; PostgreSQL has no such
    operator, so the generated query fails to parse. See
    docs/research/gap-054-table-collection.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _TABLE_OPERATOR_RE.finditer(visible):
        findings.append(
            Finding(
                detector="table_collection",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="TABLE(",
                message=_MESSAGE,
            )
        )

    return findings
