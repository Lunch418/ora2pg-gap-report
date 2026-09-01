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
_SET_RE = re.compile(r"\bSET\s*\(", re.IGNORECASE)

_MESSAGE = (
    "SET('a','b',...) — тип MySQL/MariaDB для набора значений: в столбце "
    "может лежать любое подмножество перечисленного списка сразу "
    "(хранится битовой маской). ora2pg (-m) отображает его в обычный "
    "text (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-086-mysql-set-type.md). Ошибки нет ни на загрузке, "
    "ни потом, и уже накопленные данные переносятся как есть — теряется "
    "ровно проверка: после миграции в столбец можно записать любую "
    "строку, включая значение не из списка и мусор. Severity здесь "
    "medium, а не high, в отличие от родственного ENUM (GAP-068): ENUM "
    "ломает загрузку схемы наглухо, а тут схема поднимается и работает, "
    "и вопрос только в проверке будущих записей. Восстанавливается либо "
    "CHECK-ограничением, либо массивом с проверкой на допустимые "
    "элементы, либо отдельной таблицей связей — что честнее всего, если "
    "значений много."
)


def find_mysql_set_columns(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB SET(...) multi-value columns. ora2pg -m maps
    them onto plain text, which loads and works but validates nothing --
    any string at all becomes storable afterwards. See docs/research/
    gap-086-mysql-set-type.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        span = table_column_definition_list(clean, m.end())
        if span is None:
            continue  # bare CTAS with no column-definition list at all
        open_pos, close_pos = span
        column_list = clean[open_pos + 1 : close_pos]

        for col_match in _SET_RE.finditer(column_list):
            findings.append(
                Finding(
                    detector="mysql_set_type",
                    severity="medium",
                    object_name=m.group(1).upper(),
                    line=line_at(clean, open_pos + 1 + col_match.start()),
                    snippet="SET(...)",
                    message=_MESSAGE,
                )
            )

    return findings
