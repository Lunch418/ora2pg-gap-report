import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

_MERGE_RE = re.compile(r"\bMERGE\s+INTO\b", re.IGNORECASE)
# No identifier between DELETE and WHERE: an ordinary standalone DELETE
# always needs a table reference there ('DELETE [FROM] table WHERE ...'),
# even with FROM omitted (Oracle allows that). 'DELETE WHERE' with nothing
# in between only occurs in MERGE's own compound
# 'UPDATE SET ... [WHERE ...] DELETE WHERE ...' clause under WHEN MATCHED —
# this pattern is unambiguous without needing to parse WHEN MATCHED's
# boundaries explicitly.
_DELETE_WHERE_RE = re.compile(r"\bDELETE\s+WHERE\b", re.IGNORECASE)

_MESSAGE = (
    "MERGE ... WHEN MATCHED THEN UPDATE SET ... DELETE WHERE ... — "
    "составная Oracle-конструкция, удаляющая часть только что "
    "обновлённых строк. ora2pg копирует её как есть (подтверждено "
    "реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-002-merge-delete-clause.md), а в MERGE PostgreSQL "
    "(15+) такого нет — каждая ветка WHEN является одним действием "
    "(UPDATE/DELETE/INSERT/DO NOTHING), а не составным UPDATE-затем-DELETE. "
    "Подтверждено на реальном PostgreSQL 16: CREATE PROCEDURE проходит без "
    "единой ошибки (ora2pg отключает check_function_bodies в своём "
    "выводе), синтаксическая ошибка всплывает только при первом реальном "
    "вызове — то есть в проде, а не на этапе компиляции. Обычный MERGE "
    "(UPDATE+INSERT, без DELETE WHERE) — не проблема, конвертируется и "
    "выполняется корректно. Нужно вручную разбить на две ветки WHEN "
    "MATCHED со взаимоисключающими условиями вместо составной конструкции."
)


def find_merge_delete_clauses(source: str) -> list[Finding]:
    """Detect Oracle's MERGE ... DELETE WHERE compound clause. Plain MERGE
    (UPDATE + INSERT branches, no DELETE WHERE) is not flagged — it
    converts and runs correctly (confirmed against a real PostgreSQL 16
    server, see docs/research/gap-002-merge-delete-clause.md) and is not a
    gap.

    Unlike autonomous_tx (restricted to PACKAGE BODY routines), a MERGE
    outside any package body is still flagged — MERGE is just as common in
    standalone procedures/functions and trigger bodies. object_name uses
    plsql_lex.enclosing_object_name(), best-effort: PACKAGE_BODY.ROUTINE,
    a bare standalone routine/trigger name, or "UNKNOWN" if nothing named
    encloses it at all.
    """
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for merge_match in _MERGE_RE.finditer(visible):
        stmt_end = visible.find(";", merge_match.end())
        if stmt_end == -1:
            stmt_end = len(visible)
        statement = visible[merge_match.start() : stmt_end]

        delete_match = _DELETE_WHERE_RE.search(statement)
        if not delete_match:
            continue

        absolute_pos = merge_match.start() + delete_match.start()

        findings.append(
            Finding(
                detector="merge_delete_clause",
                severity="high",
                object_name=enclosing_object_name(name_index, merge_match.start()),
                line=line_at(clean, absolute_pos),
                snippet=delete_match.group(0).strip(),
                message=_MESSAGE,
            )
        )

    return findings
