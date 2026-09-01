import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

# The table *option* AUTO_INCREMENT=<n> (the next value the table will
# hand out), not the column *attribute* AUTO_INCREMENT -- the '=' is what
# separates the two, and the column attribute converts fine (it becomes
# serial), so matching it here would be a false positive on every
# auto-increment table in existence.
_AUTO_INCREMENT_START_RE = re.compile(r"\bAUTO_INCREMENT\s*=\s*(\d+)", re.IGNORECASE)

_MESSAGE = (
    "AUTO_INCREMENT=<n> в опциях таблицы — следующее значение, которое "
    "выдаст счётчик; в дампе непустой таблицы оно всегда больше "
    "максимального существующего id. ora2pg (-m) переносит сам столбец "
    "корректно (он становится serial), но стартовое значение теряет: в "
    "выводе нет ни ALTER SEQUENCE ... RESTART WITH <n>, ни setval() "
    "(подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-080-mysql-auto-increment-start.md). Схема "
    "загружается без единой ошибки, и последовательность начинает "
    "отсчёт с 1 — то есть с значений, которые в перенесённых данных уже "
    "заняты. Первая же вставка после миграции падает на нарушении "
    "первичного ключа, и так до тех пор, пока счётчик не догонит "
    "реальные данные. Чинится одной строкой на таблицу после загрузки "
    "данных: SELECT setval(pg_get_serial_sequence('<таблица>', "
    "'<столбец>'), (SELECT max(<столбец>) FROM <таблица>))."
)


def find_mysql_auto_increment_start(source: str) -> list[Finding]:
    """Detect the MySQL `AUTO_INCREMENT=<n>` *table option*. ora2pg -m
    converts the column to serial but drops the starting value, so the
    PostgreSQL sequence restarts at 1 and collides with already-migrated
    rows on the first insert. The column attribute `AUTO_INCREMENT`
    (without `=`) converts correctly and is deliberately not flagged. See
    docs/research/gap-080-mysql-auto-increment-start.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _AUTO_INCREMENT_START_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_auto_increment_start",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=f"AUTO_INCREMENT={m.group(1)}",
                message=_MESSAGE,
            )
        )

    return findings
