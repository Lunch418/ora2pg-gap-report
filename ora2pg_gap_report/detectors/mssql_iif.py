import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_PATTERN_RE = re.compile(r"\bIIF\s*\(", re.IGNORECASE)

_MESSAGE = (
    "IIF(<условие>, <если да>, <если нет>) — тернарный выбор в T-SQL. "
    "ora2pg (-M) копирует вызов в тело процедуры дословно (подтверждено "
    "реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/"
    "gap-098-mssql-iif.md). Функции IIF в PostgreSQL нет, и при первом "
    "же реальном вызове процедура падает; загрузка проходит чисто, "
    "потому что ora2pg выставляет в своём выводе check_function_bodies "
    "= false. Показательно, что в том же операторе ora2pg соседний "
    "CHARINDEX перевести пытается (и делает это неверно, см. GAP-100), "
    "то есть IIF просто не входит в его таблицу соответствий. "
    "Переписывается на CASE WHEN <условие> THEN <если да> ELSE <если "
    "нет> END."
)


def find_mssql_iif(source: str) -> list[Finding]:
    """Detect T-SQL's IIF(). ora2pg -M copies the call through
    unchanged -- notably, it does translate the sibling CHARINDEX in the
    same statement, just wrongly (GAP-100) -- and PostgreSQL has no IIF,
    so the routine loads cleanly and fails on its first call. See
    docs/research/gap-098-mssql-iif.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_iif",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="IIF(...)",
                message=_MESSAGE,
            )
        )

    return findings
