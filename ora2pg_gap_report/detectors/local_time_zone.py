import re

from ..models import Finding
from ..plsql_lex import (
    line_at,
    mask_strings_and_comments,
    qualified_name_pattern,
    table_column_definition_list,
)

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# TIMESTAMP [(p)] WITH LOCAL TIME ZONE, specifically -- plain
# `TIMESTAMP WITH TIME ZONE` (no LOCAL) is a different Oracle type that
# ora2pg maps correctly onto PostgreSQL's timestamptz, and must not be
# flagged. The optional precision is part of the match but isn't captured
# separately: the finding is about the type's time-zone semantics, not
# its fractional-second precision.
_LTZ_COLUMN_RE = re.compile(
    r"\bTIMESTAMP\b(?:\s*\(\s*\d+\s*\))?\s+WITH\s+LOCAL\s+TIME\s+ZONE\b",
    re.IGNORECASE,
)

_MESSAGE = (
    "TIMESTAMP WITH LOCAL TIME ZONE — Oracle хранит момент времени в "
    "нормализованном виде и на чтении автоматически пересчитывает его в "
    "часовой пояс текущей сессии. ora2pg конвертирует такой столбец в "
    "простой timestamp — БЕЗ часового пояса (подтверждено реальным "
    "прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-044-local-time-zone.md). Ошибки не будет никогда: "
    "CREATE TABLE проходит, INSERT проходит, SELECT возвращает значение. "
    "Но пересчёт в часовой пояс сессии молча исчезает — одно и то же "
    "значение теперь отдаётся одинаковым во всех сессиях, независимо от "
    "их TIME ZONE, тогда как в Oracle оно сдвигалось. Для системы, где "
    "клиенты в разных поясах, это тихое расхождение в данных, которое "
    "проявится только как жалоба пользователя на неверное время. "
    "Правильная замена в PostgreSQL — timestamptz (timestamp with time "
    "zone): именно он делает то же, что Oracle LTZ."
)


def find_local_time_zone_columns(source: str) -> list[Finding]:
    """Detect Oracle's TIMESTAMP WITH LOCAL TIME ZONE used as a column
    type. ora2pg converts it to a plain `timestamp` (no time zone at
    all), silently dropping the session-time-zone normalisation that is
    the entire point of the Oracle type -- PostgreSQL's `timestamptz`
    would be the faithful target. No error is ever raised. See
    docs/research/gap-044-local-time-zone.md.

    object_name is the table's own name (schema-level DDL) -- same
    reasoning as rowid_type.py, whose column-list scoping this mirrors:
    only the '(...)' column-definition list right after the table name is
    searched, so a trailing AS SELECT clause can't be misread as a type
    declaration."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        span = table_column_definition_list(clean, m.end())
        if span is None:
            continue  # bare CTAS with no column-definition list at all
        open_pos, close_pos = span
        column_list = clean[open_pos + 1 : close_pos]

        for col_match in _LTZ_COLUMN_RE.finditer(column_list):
            findings.append(
                Finding(
                    detector="local_time_zone",
                    severity="high",
                    object_name=m.group(1).upper(),
                    line=line_at(clean, open_pos + 1 + col_match.start()),
                    snippet=re.sub(r"\s+", " ", col_match.group(0).strip().upper()),
                    message=_MESSAGE,
                )
            )

    return findings
