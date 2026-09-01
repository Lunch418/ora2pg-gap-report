import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_PATTERN_RE = re.compile(r"\bCHARINDEX\s*\(", re.IGNORECASE)

_MESSAGE = (
    "CHARINDEX(<что искать>, <где искать>) — поиск подстроки в T-SQL. "
    "В отличие от прочих встроенных функций этой партии, ora2pg (-M) "
    "её переводить пытается — и выбирает верную цель, position(... in "
    "...), — но удваивает кавычки вокруг искомой строки: из "
    "CHARINDEX(\'abc\', @nm) получается position(\'\'abc\'\' in p_nm) "
    "(подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-100-mssql-charindex.md). Это уже не валидный SQL: "
    "разбор падает с \'syntax error at or near \"abc\"\'. Загрузка "
    "проходит чисто (check_function_bodies = false в выводе ora2pg), "
    "ошибка вылезает при первом вызове. Чинится снятием лишних кавычек: "
    "position(\'abc\' in p_nm). Имейте в виду, что у CHARINDEX есть "
    "третий аргумент — позиция начала поиска, — которому у position() "
    "прямого соответствия нет и который переносится через substring()."
)


def find_mssql_charindex(source: str) -> list[Finding]:
    """Detect T-SQL's CHARINDEX(). Unlike the other builtins in this
    batch ora2pg -M does translate it -- into position(...) -- but
    doubles the quotes around the search string, producing invalid SQL,
    so the routine loads cleanly and fails on its first call. See
    docs/research/gap-100-mssql-charindex.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_charindex",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="CHARINDEX(...)",
                message=_MESSAGE,
            )
        )

    return findings
