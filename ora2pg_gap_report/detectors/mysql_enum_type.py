import re

from ..models import Finding
from ..mysql_lex import (
    line_at,
    mask_strings_and_comments,
    qualified_name_pattern,
    table_column_definition_list,
)

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_ENUM_RE = re.compile(r"\bENUM\s*\(", re.IGNORECASE)

_MESSAGE = (
    "ENUM(...) — столбец с перечислимым типом MySQL/MariaDB. ora2pg (-m) "
    "синтезирует под него именованный PostgreSQL-тип "
    "<таблица>_<столбец>_t и подставляет это имя в определение столбца, "
    "но сам оператор CREATE TYPE ... AS ENUM (...), которым этот тип "
    "должен быть объявлен, в вывод не попадает — подтверждено реальным "
    "прогоном ora2pg 25.0 + PostgreSQL 16 (docs/research/"
    "gap-068-mysql-enum-type.md). CREATE TABLE падает немедленно, при "
    "загрузке схемы: 'type \"<таблица>_<столбец>_t\" does not exist'. "
    "Значения перечисления при этом никуда не теряются — они видны прямо "
    "в исходном ENUM(...), — так что руками нужно лишь вставить "
    "недостающий CREATE TYPE перед CREATE TABLE."
)


def find_mysql_enum_columns(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB ENUM(...) columns. ora2pg -m synthesizes a
    named PostgreSQL enum type for each one but never emits the CREATE
    TYPE statement that type needs, so the generated CREATE TABLE
    references a type that was never declared and fails to load. See
    docs/research/gap-068-mysql-enum-type.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        span = table_column_definition_list(clean, m.end())
        if span is None:
            continue  # bare CTAS with no column-definition list at all
        open_pos, close_pos = span
        column_list = clean[open_pos + 1 : close_pos]

        for col_match in _ENUM_RE.finditer(column_list):
            findings.append(
                Finding(
                    detector="mysql_enum_type",
                    severity="high",
                    object_name=m.group(1).upper(),
                    line=line_at(clean, open_pos + 1 + col_match.start()),
                    snippet="ENUM(...)",
                    message=_MESSAGE,
                )
            )

    return findings
