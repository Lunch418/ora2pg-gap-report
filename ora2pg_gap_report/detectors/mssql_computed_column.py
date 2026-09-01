import re

from ..models import Finding
from ..mssql_lex import (
    line_at,
    mask_strings_and_comments,
    normalize_name,
    qualified_name_pattern,
    table_column_definition_list,
)

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_PATTERN_RE = re.compile(r"\bAS\s*\(", re.IGNORECASE)

_MESSAGE = (
    "Вычисляемый столбец (<имя> AS (<выражение>), с PERSISTED или без) "
    "— столбец SQL Server, значение которого считается из других "
    "столбцов. ora2pg (-M) строит под него триггер BEFORE INSERT OR "
    "UPDATE — сам по себе подход рабочий, — но тип самого столбца "
    "выводит как citext независимо от того, что считает выражение "
    "(подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-104-mssql-computed-column.md). Проверено: для "
    "total AS (price * qty) PERSISTED, где price numeric(10,2) и qty "
    "int, в готовой таблице столбец total имеет тип citext, то есть "
    "текст. Ошибки нет ни на загрузке, ни при вставке — значение "
    "посчитается и запишется, — но дальше это уже строка: сортировка "
    "идёт лексикографически (\'100\' < \'20\'), сравнение с числом и "
    "SUM() по столбцу падают или дают не то. Кроме того, в тело триггера "
    "попадает служебное слово PERSISTED, которое PostgreSQL молча "
    "трактует как псевдоним столбца. Чинится заменой типа столбца на "
    "тот, что реально считает выражение, а лучше — переносом на "
    "штатный GENERATED ALWAYS AS (...) STORED."
)


def find_mssql_computed_columns(source: str) -> list[Finding]:
    """Detect T-SQL computed columns (`col AS (expr)`, with or without
    PERSISTED). ora2pg -M builds a BEFORE trigger for them but types the
    column as citext regardless of what the expression computes, so a
    numeric computation ends up stored as case-insensitive text. See
    docs/research/gap-104-mssql-computed-column.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        span = table_column_definition_list(clean, m.end())
        if span is None:
            continue  # CREATE TABLE ... AS SELECT, no column-definition list
        open_pos, close_pos = span
        column_list = clean[open_pos + 1 : close_pos]

        for col_match in _PATTERN_RE.finditer(column_list):
            findings.append(
                Finding(
                    detector="mssql_computed_column",
                    severity="high",
                    object_name=normalize_name(m.group(1)).upper(),
                    line=line_at(clean, open_pos + 1 + col_match.start()),
                    snippet="AS (...)",
                    message=_MESSAGE,
                )
            )

    return findings
