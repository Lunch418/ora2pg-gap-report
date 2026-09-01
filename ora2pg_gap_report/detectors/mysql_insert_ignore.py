import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_INSERT_IGNORE_RE = re.compile(r"\bINSERT\s+IGNORE\b", re.IGNORECASE)

_MESSAGE = (
    "INSERT IGNORE — MySQL/MariaDB-специфичная форма вставки, которая "
    "превращает ошибки в предупреждения и молча пропускает проблемные "
    "строки. ora2pg (-m) копирует оператор в тело процедуры/функции "
    "дословно (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL "
    "16, docs/research/gap-077-mysql-insert-ignore.md). Такого синтаксиса "
    "у INSERT в PostgreSQL нет. CREATE PROCEDURE/FUNCTION проходит без "
    "ошибок — ora2pg выставляет в своём выводе check_function_bodies = "
    "false, поэтому тело не разбирается на загрузке, — и падение "
    "происходит при первом же реальном вызове. Ближайший аналог — "
    "INSERT ... ON CONFLICT DO NOTHING, но он уже по охвату: IGNORE в "
    "MySQL глушит не только конфликт уникальности, но и другие ошибки "
    "вставки, вплоть до обрезания слишком длинных значений и подстановки "
    "нулей вместо некорректных дат. Если код полагался именно на это "
    "широкое поведение, дословный перевод изменит смысл — стоит "
    "разобраться, какие именно ошибки там глушились."
)


def find_mysql_insert_ignore(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's INSERT IGNORE. ora2pg -m copies it through
    unchanged; PostgreSQL has no such INSERT syntax, so the containing
    routine loads cleanly and fails on its first call. ON CONFLICT DO
    NOTHING is narrower than IGNORE, not an exact equivalent. See
    docs/research/gap-077-mysql-insert-ignore.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _INSERT_IGNORE_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_insert_ignore",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="INSERT IGNORE",
                message=_MESSAGE,
            )
        )

    return findings
