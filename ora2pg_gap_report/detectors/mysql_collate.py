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
_COLLATE_RE = re.compile(r"\b(COLLATE|CHARACTER\s+SET)\s+\w+", re.IGNORECASE)

_MESSAGE = (
    "COLLATE / CHARACTER SET на столбце — правило сравнения и сортировки "
    "строк. ora2pg (-m) выбрасывает эту часть определения столбца из "
    "вывода целиком (подтверждено реальным прогоном ora2pg 25.0 + "
    "PostgreSQL 16, docs/research/gap-085-mysql-collate.md). Ошибки не "
    "будет ни на загрузке, ни потом, но сравнение строк молча меняет "
    "смысл: типовые для MySQL правила вида utf8mb4_general_ci / "
    "utf8mb4_0900_ai_ci регистронезависимы, а сравнение в PostgreSQL по "
    "умолчанию — регистрозависимо. Проверено на живых данных: строка "
    "'Alice', найденная в MySQL запросом WHERE name = 'alice', после "
    "миграции не находится вообще (0 строк). То есть ломается не схема, а "
    "выдача запросов — логины, поиск по имени, проверки уникальности "
    "начинают вести себя иначе, и заметно это только в бою. "
    "Восстанавливается либо явным COLLATE на столбце (в PostgreSQL "
    "доступны ICU-правила с нужной чувствительностью), либо типом citext, "
    "либо приведением обеих сторон сравнения к lower()."
)


def find_mysql_collations(source: str) -> list[Finding]:
    """Detect per-column COLLATE/CHARACTER SET clauses in a MySQL CREATE
    TABLE. ora2pg -m drops them, silently turning MySQL's usual
    case-insensitive collation into PostgreSQL's case-sensitive default --
    no error, just different query results. See docs/research/
    gap-085-mysql-collate.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        span = table_column_definition_list(clean, m.end())
        if span is None:
            continue  # bare CTAS with no column-definition list at all
        open_pos, close_pos = span
        column_list = clean[open_pos + 1 : close_pos]

        for col_match in _COLLATE_RE.finditer(column_list):
            findings.append(
                Finding(
                    detector="mysql_collate",
                    severity="high",
                    object_name=m.group(1).upper(),
                    line=line_at(clean, open_pos + 1 + col_match.start()),
                    snippet=col_match.group(0),
                    message=_MESSAGE,
                )
            )

    return findings
