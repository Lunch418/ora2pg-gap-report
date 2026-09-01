import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_PATTERN_RE = re.compile(r"\b(RAISERROR|THROW)\b", re.IGNORECASE)

_MESSAGE = (
    "RAISERROR / THROW — операторы возбуждения ошибки в T-SQL. ora2pg "
    "(-M) копирует оба в тело процедуры дословно (подтверждено реальным "
    "прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/"
    "gap-093-mssql-raiserror.md). В PL/pgSQL нет ни того, ни другого. "
    "Загрузка проходит чисто — ora2pg выставляет в своём выводе "
    "check_function_bodies = false, — и падение происходит при первом же "
    "реальном вызове. Переписывается на RAISE EXCEPTION \'<текст>\' "
    "USING ERRCODE = \'<sqlstate>\'. При переносе стоит помнить о "
    "разнице: severity в RAISERROR (второй аргумент) в PostgreSQL "
    "соответствует не коду ошибки, а уровню сообщения — RAISE NOTICE / "
    "WARNING / EXCEPTION, — а номера ошибок из THROW (>= 50000) нужно "
    "отобразить на пятизначные SQLSTATE самостоятельно."
)


def find_mssql_raiserror(source: str) -> list[Finding]:
    """Detect T-SQL RAISERROR and THROW. ora2pg -M copies both through
    unchanged; PL/pgSQL has neither, so the containing routine loads
    cleanly and fails on its first call. See docs/research/
    gap-093-mssql-raiserror.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_raiserror",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=m.group(1).upper(),
                message=_MESSAGE,
            )
        )

    return findings
