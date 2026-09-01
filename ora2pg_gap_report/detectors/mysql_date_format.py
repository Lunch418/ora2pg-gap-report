import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_DATE_FORMAT_RE = re.compile(r"\bDATE_FORMAT\s*\(", re.IGNORECASE)

_MESSAGE = (
    "DATE_FORMAT(<дата>, <формат>) — форматирование даты в строку по "
    "MySQL-овским спецификаторам (%Y, %m, %d, %H, %i, %s). ora2pg (-m) "
    "пытается перевести вызов и выдаёт то, что вызовом функции уже не "
    "является: имени to_char в выводе нет вообще, остаётся голая скобка "
    "с двумя выражениями через запятую — (d::varchar::timestamp, "
    "'YYYY-MM-%d HH24:MI:SS'), то есть конструктор строки-кортежа. "
    "Заодно переведены не все спецификаторы: %Y/%m/%H/%i/%s стали "
    "YYYY/MM/HH24/MI/SS, а %d остался как был (подтверждено реальным "
    "прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/"
    "gap-081-mysql-date-format.md). Хуже всего то, что ошибки не будет "
    "ни на одном этапе: и загрузка, и вызов проходят успешно, потому "
    "что кортеж — совершенно законное выражение. Проверено на живых "
    "данных: вместо строки 2024-03-05 00:00:00 запрос возвращает пару "
    "из самой даты и недопереведённой строки формата. То есть в "
    "отчётах, выгрузках и API-ответах молча оказывается не то, что "
    "было. Чинится переписыванием на to_char(<дата>, 'YYYY-MM-DD "
    "HH24:MI:SS'), и каждый спецификатор формата стоит сверить вручную."
)


def find_mysql_date_format(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's DATE_FORMAT(). ora2pg -m emits a bare
    parenthesised pair -- a row constructor -- with the to_char function
    name missing entirely and %d left untranslated, so nothing errors at
    any stage and the query silently returns a tuple instead of a
    formatted string. See docs/research/gap-081-mysql-date-format.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _DATE_FORMAT_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_date_format",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="DATE_FORMAT(...)",
                message=_MESSAGE,
            )
        )

    return findings
