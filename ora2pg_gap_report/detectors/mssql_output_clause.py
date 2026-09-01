import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_PATTERN_RE = re.compile(r"\bOUTPUT\s+(?:INSERTED|DELETED)\.", re.IGNORECASE)

_MESSAGE = (
    "OUTPUT INSERTED.<столбец> / OUTPUT DELETED.<столбец> — возврат "
    "затронутых строк прямо из INSERT/UPDATE/DELETE в T-SQL. ora2pg "
    "(-M) копирует оговорку в тело процедуры дословно (подтверждено "
    "реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/"
    "gap-097-mssql-output-clause.md). В PostgreSQL та же идея пишется "
    "как RETURNING, и слова OUTPUT он не понимает. Загрузка проходит "
    "чисто (check_function_bodies = false в выводе ora2pg), падение — "
    "при первом вызове. Переписывается на RETURNING <столбец>, но с "
    "оглядкой на две вещи: RETURNING не различает INSERTED и DELETED "
    "(для UPDATE он возвращает новые значения — старые придётся брать "
    "иначе), и в отличие от OUTPUT ... INTO <таблица> его результат "
    "нельзя направить в таблицу одним оператором."
)


def find_mssql_output_clause(source: str) -> list[Finding]:
    """Detect T-SQL's OUTPUT INSERTED/DELETED clause. ora2pg -M copies
    it through unchanged; PostgreSQL spells the same idea as RETURNING,
    so the containing routine loads cleanly and fails on its first call.
    See docs/research/gap-097-mssql-output-clause.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_output_clause",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=m.group(0).upper(),
                message=_MESSAGE,
            )
        )

    return findings
