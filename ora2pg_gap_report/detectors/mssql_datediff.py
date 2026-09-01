import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_PATTERN_RE = re.compile(r"\bDATEDIFF\s*\(", re.IGNORECASE)

_MESSAGE = (
    "DATEDIFF(<единица>, <начало>, <конец>) — разница дат в T-SQL. "
    "ora2pg (-M) копирует вызов в тело процедуры дословно (подтверждено "
    "реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/"
    "gap-099-mssql-datediff.md), хотя соседние DATEADD и DATEPART в том "
    "же операторе переводит правильно — в арифметику с INTERVAL и в "
    "date_part(). Функции DATEDIFF в PostgreSQL нет; загрузка проходит "
    "чисто (check_function_bodies = false в выводе ora2pg), падение — "
    "при первом вызове. Переписывается через вычитание: разница в днях "
    "— (<конец>::date - <начало>::date), в остальных единицах — через "
    "EXTRACT(EPOCH FROM (<конец> - <начало>)) с делением. Обратите "
    "внимание на семантику: T-SQL DATEDIFF считает пересечённые границы "
    "единиц, а не полные интервалы, поэтому DATEDIFF(year, ...) между "
    "31 декабря и 1 января даёт 1 — прямое вычитание даст 0."
)


def find_mssql_datediff(source: str) -> list[Finding]:
    """Detect T-SQL's DATEDIFF(). ora2pg -M copies it through
    unchanged, even though it does convert DATEADD and DATEPART in the
    same statement, so the routine loads cleanly and fails on its first
    call. See docs/research/gap-099-mssql-datediff.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_datediff",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="DATEDIFF(...)",
                message=_MESSAGE,
            )
        )

    return findings
