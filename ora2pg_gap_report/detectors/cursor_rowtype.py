import re

from ..models import Finding
from ..plsql_lex import (
    IDENTIFIER,
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

_CURSOR_DECL_RE = re.compile(rf"\bCURSOR\s+({IDENTIFIER})\b", re.IGNORECASE)
# `<name>%ROWTYPE`, where <name> is captured so it can be checked against
# the cursors declared in the same source. A qualified `schema.table` or a
# bare table name is the supported form and must not be flagged, so the
# name is deliberately matched without a dot.
_ROWTYPE_RE = re.compile(rf"(?<![.\w])({IDENTIFIER})\s*%\s*ROWTYPE", re.IGNORECASE)

_MESSAGE = (
    "<курсор>%ROWTYPE — объявление переменной по структуре курсора. "
    "ora2pg копирует конструкцию в вывод как есть (подтверждено реальным "
    "прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-064-cursor-rowtype.md). PL/pgSQL понимает "
    "%ROWTYPE только от таблицы или представления, но не от курсора, "
    "поэтому имя курсора трактуется как имя отношения и при первом же "
    "вызове процедура падает с 'relation \"c\" does not exist'. Сама "
    "загрузка проходит чисто: ora2pg выставляет в своём выводе "
    "check_function_bodies = false, так что тело не разбирается на "
    "CREATE PROCEDURE. Заменяется на RECORD — в PL/pgSQL переменная типа "
    "RECORD принимает строку любого курсора, и FETCH в неё работает без "
    "изменений. Обратите внимание: обычное <таблица>%ROWTYPE ora2pg "
    "переносит корректно, и этот детектор его не помечает — только "
    "%ROWTYPE от курсора, объявленного в том же файле."
)


def find_cursor_rowtype(source: str) -> list[Finding]:
    """Detect PL/SQL `<cursor>%ROWTYPE` declarations. PL/pgSQL supports
    %ROWTYPE only against a table or view, so ora2pg's verbatim copy
    fails at first call with 'relation ... does not exist'. Only names
    that are actually declared as a CURSOR in the same source are
    flagged, so ordinary `<table>%ROWTYPE` -- which converts correctly --
    stays clean. See docs/research/gap-064-cursor-rowtype.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)

    cursor_names = {m.group(1).upper() for m in _CURSOR_DECL_RE.finditer(visible)}
    if not cursor_names:
        return []

    findings: list[Finding] = []
    for m in _ROWTYPE_RE.finditer(visible):
        name = m.group(1).upper()
        if name not in cursor_names:
            continue
        findings.append(
            Finding(
                detector="cursor_rowtype",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=f"{m.group(1).lower()}%ROWTYPE",
                message=_MESSAGE,
            )
        )

    return findings
