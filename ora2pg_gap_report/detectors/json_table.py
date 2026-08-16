import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

_JSON_TABLE_RE = re.compile(r"\bJSON_TABLE\s*\(", re.IGNORECASE)

_MESSAGE = (
    "JSON_TABLE(...) — табличная проекция JSON-документа в реляционные "
    "строки/столбцы. ora2pg копирует вызов как есть (подтверждено "
    "реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-017-json-table.md). На PostgreSQL 16 и старше "
    "падает с синтаксической ошибкой прямо на COLUMNS — функции "
    "JSON_TABLE в PostgreSQL нет вообще (появилась только в PostgreSQL 17, "
    "и то с другим синтаксисом секции COLUMNS, не идентичным Oracle — не "
    "проверялось эмпирически в этом исследовании, но использовать как "
    "прямую замену без сверки нельзя). До PostgreSQL 17 нужен полностью "
    "ручной переход на jsonb_to_recordset()/jsonb_array_elements() с "
    "явным приведением типов."
)


def find_json_table_calls(source: str) -> list[Finding]:
    """Detect Oracle's JSON_TABLE(...) SQL/JSON function. ora2pg passes it
    through unchanged; PostgreSQL 16 and earlier have no such function at
    all (PostgreSQL 17 added JSON_TABLE, but with a COLUMNS syntax not
    verified here to match Oracle's own). See
    docs/research/gap-017-json-table.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _JSON_TABLE_RE.finditer(visible):
        findings.append(
            Finding(
                detector="json_table",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="JSON_TABLE(...)",
                message=_MESSAGE,
            )
        )

    return findings
