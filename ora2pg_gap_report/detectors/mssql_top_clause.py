import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_PATTERN_RE = re.compile(r"\bTOP\s*\(?\s*(?:\d+|@\w+)", re.IGNORECASE)

_MESSAGE = (
    "SELECT TOP <n> — ограничение числа строк в T-SQL. ora2pg (-M) "
    "копирует конструкцию в тело процедуры дословно (подтверждено "
    "реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/"
    "gap-095-mssql-top-clause.md). В PostgreSQL оператора TOP нет "
    "вообще, и разбор падает на числе сразу за ним: \'syntax error at "
    "or near \"10\"\'. Загрузка при этом проходит чисто "
    "(check_function_bodies = false в выводе ora2pg), ошибка вылезает "
    "при первом вызове. Переписывается на LIMIT <n> в конце запроса. "
    "Отдельно проверьте TOP без ORDER BY: в T-SQL так пишут часто, и "
    "при переносе на LIMIT порядок строк остаётся столь же "
    "неопределённым — если на него полагались, нужен явный ORDER BY. "
    "Форма TOP (<n>) PERCENT прямого аналога не имеет вовсе и требует "
    "отдельного пересчёта."
)


def find_mssql_top_clause(source: str) -> list[Finding]:
    """Detect T-SQL's TOP n clause. ora2pg -M copies it through
    unchanged and PostgreSQL has no TOP at all, so the containing routine
    loads cleanly and fails on its first call. See docs/research/
    gap-095-mssql-top-clause.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_top_clause",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="TOP n",
                message=_MESSAGE,
            )
        )

    return findings
