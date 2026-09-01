import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_ON_DUP_RE = re.compile(r"\bON\s+DUPLICATE\s+KEY\s+UPDATE\b", re.IGNORECASE)

_MESSAGE = (
    "INSERT ... ON DUPLICATE KEY UPDATE — MySQL/MariaDB-специфичный "
    "upsert: обновить существующую строку, если вставка конфликтует с "
    "уникальным ключом/PRIMARY KEY, иначе вставить новую. ora2pg (-m) "
    "копирует весь оператор ON DUPLICATE KEY UPDATE в тело процедуры/"
    "функции дословно, без какого-либо преобразования — подтверждено "
    "реальным прогоном ora2pg 25.0 + PostgreSQL 16 (docs/research/"
    "gap-070-mysql-on-duplicate-key-update.md). Такого синтаксиса у "
    "INSERT в PostgreSQL нет вообще. CREATE PROCEDURE/FUNCTION при этом "
    "проходит без ошибок — ora2pg выставляет в своём выводе "
    "check_function_bodies = false, поэтому тело не разбирается на "
    "загрузке, — и падение происходит при первом же реальном вызове: "
    "'syntax error at or near \"DUPLICATE\"'. Переписывается на "
    "INSERT ... ON CONFLICT (<уникальный_ключ>) DO UPDATE SET ...."
)


def find_mysql_on_duplicate_key_update(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's `INSERT ... ON DUPLICATE KEY UPDATE`
    upsert clause. ora2pg -m copies it through unchanged and PostgreSQL
    has no such INSERT syntax at all, so the containing procedure/
    function loads cleanly (bodies are not checked) and then fails on
    its first call. See docs/research/
    gap-070-mysql-on-duplicate-key-update.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _ON_DUP_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_on_duplicate_key_update",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="ON DUPLICATE KEY UPDATE",
                message=_MESSAGE,
            )
        )

    return findings
