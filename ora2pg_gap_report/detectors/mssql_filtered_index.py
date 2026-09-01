import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

# A filtered index is a CREATE INDEX carrying a WHERE clause; the
# bounded non-greedy body keeps the match inside one statement.
_PATTERN_RE = re.compile(r"\bCREATE\s+(?:UNIQUE\s+)?(?:CLUSTERED\s+|NONCLUSTERED\s+)?INDEX\b[^;]{0,300}?\bWHERE\b", re.IGNORECASE)

_MESSAGE = (
    "Фильтрованный индекс (CREATE INDEX ... WHERE <условие>) — индекс "
    "по части строк таблицы. ora2pg (-M) выбрасывает такой оператор "
    "целиком: в выводе не появляется никакого индекса вообще "
    "(подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-101-mssql-filtered-index.md). Обиднее всего, что "
    "переносить тут почти нечего: в PostgreSQL есть ровно такие же "
    "частичные индексы и ровно с тем же синтаксисом — CREATE INDEX ... "
    "ON ... WHERE ..., — а обычный CREATE NONCLUSTERED INDEX ... "
    "INCLUDE (...) тот же ora2pg в том же прогоне переносит корректно. "
    "Ошибки не будет ни на загрузке, ни потом: схема поднимется без "
    "индекса, и разница проявится как деградация планов на больших "
    "таблицах, а если индекс был UNIQUE — ещё и как исчезнувшее "
    "ограничение уникальности. Восстанавливается дословным переносом "
    "оператора после загрузки схемы."
)


def find_mssql_filtered_indexes(source: str) -> list[Finding]:
    """Detect T-SQL filtered indexes (`CREATE INDEX ... WHERE ...`).
    ora2pg -M drops the whole statement, emitting no index at all, even
    though PostgreSQL supports partial indexes with the same syntax. See
    docs/research/gap-101-mssql-filtered-index.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_filtered_index",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="filtered INDEX",
                message=_MESSAGE,
            )
        )

    return findings
