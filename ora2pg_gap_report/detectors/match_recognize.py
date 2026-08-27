import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

# Anchored on the opening paren MATCH_RECOGNIZE always has -- a bare
# identifier called `match_recognize` (a legal Oracle column/table name)
# isn't the row-pattern-matching clause and must not be flagged.
_MATCH_RECOGNIZE_RE = re.compile(r"\bMATCH_RECOGNIZE\s*\(", re.IGNORECASE)

_MESSAGE = (
    "MATCH_RECOGNIZE (Oracle 12c+) — сопоставление строк с шаблоном прямо в "
    "SQL (PARTITION BY / ORDER BY / MEASURES / PATTERN / DEFINE): поиск "
    "последовательностей строк, соответствующих регулярному выражению над "
    "потоком, для анализа трендов, сессий, последовательностей событий. "
    "ora2pg копирует конструкцию в вывод как есть, без изменений "
    "(подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-038-match-recognize.md). У PostgreSQL нет никакого "
    "аналога row pattern matching — падает синтаксической ошибкой уже при "
    "загрузке сгенерированного DDL. Переписывается вручную через оконные "
    "функции (LAG/LEAD над разделами) плюс фильтрацию, либо через "
    "рекурсивный CTE — прямой замены на одну конструкцию не существует."
)


def find_match_recognize(source: str) -> list[Finding]:
    """Detect Oracle's MATCH_RECOGNIZE row pattern matching clause.
    ora2pg copies it into its output verbatim; PostgreSQL has no
    equivalent at all, so the generated DDL fails to load with a syntax
    error. See docs/research/gap-038-match-recognize.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _MATCH_RECOGNIZE_RE.finditer(visible):
        findings.append(
            Finding(
                detector="match_recognize",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="MATCH_RECOGNIZE",
                message=_MESSAGE,
            )
        )

    return findings
