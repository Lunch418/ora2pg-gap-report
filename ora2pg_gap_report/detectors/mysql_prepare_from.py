import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

# `PREPARE <name> FROM ...`. The FROM keyword is what distinguishes
# MySQL's spelling from PostgreSQL's own PREPARE (`PREPARE name AS
# query`), which is valid and must not be flagged -- ora2pg's output can
# legitimately contain the latter.
_PREPARE_FROM_RE = re.compile(r"\bPREPARE\s+\w+\s+FROM\b", re.IGNORECASE)

_MESSAGE = (
    "PREPARE <имя> FROM <строка> — подготовка динамического SQL в "
    "хранимой процедуре MySQL/MariaDB (обычно в связке с EXECUTE и "
    "DEALLOCATE PREPARE). ora2pg (-m) копирует конструкцию в тело "
    "процедуры дословно, лишь заменяя пользовательскую переменную "
    "@s на обычную (подтверждено реальным прогоном ora2pg 25.0 + "
    "PostgreSQL 16, docs/research/gap-078-mysql-prepare-from.md). "
    "Оператор PREPARE в PostgreSQL тоже есть, но синтаксис у него "
    "другой — PREPARE <имя> AS <запрос>, — и запрос задаётся текстом "
    "самого SQL, а не строковой переменной. Поэтому падение конкретное "
    "и узнаваемое: 'syntax error at or near \"FROM\"'. Загрузка проходит "
    "чисто (ora2pg выставляет в своём выводе check_function_bodies = "
    "false), ошибка вылезает при первом вызове. Переписывается не на "
    "PostgreSQL-овский PREPARE, а на EXECUTE <строка> внутри PL/pgSQL — "
    "это штатный способ выполнить собранный в переменной SQL; параметры "
    "передаются через USING, и это же снимает риск SQL-инъекции при "
    "склейке строки."
)


def find_mysql_prepare_from(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's `PREPARE <name> FROM <string>`. PostgreSQL
    spells its own PREPARE differently (`PREPARE name AS query`, taking
    SQL text rather than a string variable), so ora2pg -m's verbatim copy
    fails on the first call with a syntax error at FROM. PL/pgSQL's
    EXECUTE is the actual equivalent. See docs/research/
    gap-078-mysql-prepare-from.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PREPARE_FROM_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_prepare_from",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="PREPARE ... FROM",
                message=_MESSAGE,
            )
        )

    return findings
