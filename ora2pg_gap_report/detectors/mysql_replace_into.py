import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

# `INTO` is required by the match so the ordinary REPLACE(str, from, to)
# string function -- an entirely different thing, and one ora2pg handles
# fine -- can't produce a finding.
_REPLACE_INTO_RE = re.compile(r"\bREPLACE\s+INTO\b", re.IGNORECASE)

_MESSAGE = (
    "REPLACE INTO — MySQL/MariaDB-специфичный оператор: вставить строку, "
    "а если строка с таким же уникальным ключом уже есть — удалить её и "
    "вставить новую. ora2pg (-m) копирует оператор в тело процедуры/"
    "функции дословно (подтверждено реальным прогоном ora2pg 25.0 + "
    "PostgreSQL 16, docs/research/gap-076-mysql-replace-into.md). Такого "
    "оператора в PostgreSQL нет. CREATE PROCEDURE/FUNCTION проходит без "
    "ошибок — ora2pg выставляет в своём выводе check_function_bodies = "
    "false, поэтому тело не разбирается на загрузке, — и падение "
    "происходит при первом же реальном вызове. Переписывается на "
    "INSERT ... ON CONFLICT (<ключ>) DO UPDATE SET ..., но перевод не "
    "дословный, и разницу стоит держать в голове: REPLACE именно удаляет "
    "старую строку и вставляет новую, поэтому по ней срабатывают "
    "ON DELETE-триггеры и каскадные удаления дочерних строк, а не "
    "перечисленные в запросе столбцы получают значения по умолчанию, а "
    "не сохраняют прежние. ON CONFLICT DO UPDATE ведёт себя ровно "
    "наоборот, так что на таблице с внешними ключами ON DELETE CASCADE "
    "механическая замена изменит поведение."
)


def find_mysql_replace_into(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's REPLACE INTO statement. ora2pg -m copies it
    through unchanged and PostgreSQL has no such statement, so the
    containing routine loads cleanly and fails on its first call. Note
    that ON CONFLICT DO UPDATE is not an exact equivalent -- REPLACE
    deletes and re-inserts, which fires delete-side triggers/cascades.
    See docs/research/gap-076-mysql-replace-into.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _REPLACE_INTO_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_replace_into",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="REPLACE INTO",
                message=_MESSAGE,
            )
        )

    return findings
