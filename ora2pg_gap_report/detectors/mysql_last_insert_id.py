import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_LAST_INSERT_ID_RE = re.compile(r"\bLAST_INSERT_ID\s*\(", re.IGNORECASE)

_MESSAGE = (
    "LAST_INSERT_ID() — функция MySQL/MariaDB, возвращающая значение "
    "AUTO_INCREMENT, выданное последней вставкой в текущем соединении. "
    "ora2pg (-m) копирует вызов в тело процедуры/функции дословно "
    "(подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-079-mysql-last-insert-id.md). В PostgreSQL такой "
    "функции нет, и при первом же реальном вызове процедура падает с "
    "'function last_insert_id() does not exist'; загрузка при этом "
    "проходит чисто, потому что ora2pg выставляет в своём выводе "
    "check_function_bodies = false. Переписывается лучше всего на "
    "INSERT ... RETURNING <столбец> INTO <переменная> — так значение "
    "берётся прямо из выполненной вставки, без обращения к состоянию "
    "сессии. Варианты currval('<последовательность>') и lastval() тоже "
    "работают, но у lastval() своя тонкость: он относится к последней "
    "использованной последовательности вообще, а не к конкретной "
    "таблице, поэтому в процедуре, вставляющей в несколько таблиц, "
    "легко получить чужое значение."
)


def find_mysql_last_insert_id(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's LAST_INSERT_ID() function. ora2pg -m copies
    the call through unchanged and PostgreSQL has no such function, so
    the containing routine loads cleanly and fails on its first call.
    See docs/research/gap-079-mysql-last-insert-id.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _LAST_INSERT_ID_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_last_insert_id",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="LAST_INSERT_ID()",
                message=_MESSAGE,
            )
        )

    return findings
