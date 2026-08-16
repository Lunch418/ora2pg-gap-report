import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

# 'AS OF TIMESTAMP'/'AS OF SCN' -- Oracle flashback query, reading a table
# as it existed at a past point in time. No other meaning for this exact
# phrase in Oracle SQL.
_FLASHBACK_RE = re.compile(r"\bAS\s+OF\s+(TIMESTAMP|SCN)\b", re.IGNORECASE)

_MESSAGE = (
    "AS OF TIMESTAMP/SCN — flashback-запрос, читающий таблицу такой, "
    "какой она была в прошлом. ora2pg копирует конструкцию как есть "
    "(с побочным искажением текста при подстановке SYSTIMESTAMP в "
    "некоторых случаях — подтверждено реальным прогоном, "
    "docs/research/gap-011-flashback-query.md) — в PostgreSQL нет "
    "встроенного эквивалента вообще. CREATE PROCEDURE/FUNCTION проходит "
    "без ошибки, падает только при первом реальном вызове. Нужен "
    "отдельный архитектурный механизм (temporal tables через расширение, "
    "собственные таблицы истории/аудита) — не синтаксическая замена."
)


def find_flashback_queries(source: str) -> list[Finding]:
    """Detect Oracle's flashback query (AS OF TIMESTAMP/SCN). No
    PostgreSQL equivalent exists at all -- see
    docs/research/gap-011-flashback-query.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _FLASHBACK_RE.finditer(visible):
        findings.append(
            Finding(
                detector="flashback_query",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=re.sub(r"\s+", " ", m.group(0)),
                message=_MESSAGE,
            )
        )

    return findings
