import re

from ..models import Finding
from ..mssql_lex import (
    line_at,
    mask_strings_and_comments,
    normalize_name,
    qualified_name_pattern,
    table_column_definition_list,
)

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_PATTERN_RE = re.compile(r"\bCOLLATE\s+\w+", re.IGNORECASE)

_MESSAGE = (
    "COLLATE на столбце — правило сравнения и сортировки строк в "
    "SQL Server. ora2pg (-M) выбрасывает оговорку из определения "
    "столбца, а сам столбец отображает в citext — регистронезависимый "
    "тип (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-103-mssql-collation.md). Для исходных правил с "
    "_CI_ (case-insensitive) это попадание в цель, а вот для _CS_ "
    "(case-sensitive) — молчаливая подмена смысла на противоположный. "
    "Проверено на живых данных: столбец с COLLATE "
    "SQL_Latin1_General_CP1_CS_AS после миграции находит строку \'ABC\' "
    "по запросу WHERE code = \'abc\' (1 строка), тогда как SQL Server с "
    "этим правилом не нашёл бы ничего. Ошибки при этом нет ни на одном "
    "этапе — меняется только выдача запросов, и заметно это в бою: "
    "ломаются проверки уникальности, поиск по коду, сравнение "
    "идентификаторов. Чинится заменой citext на text с явным COLLATE "
    "нужной чувствительности (в PostgreSQL для этого есть ICU-правила)."
)


def find_mssql_collations(source: str) -> list[Finding]:
    """Detect per-column COLLATE clauses in T-SQL. ora2pg -M drops the
    clause and maps the column onto citext, so a case-SENSITIVE source
    collation silently becomes case-insensitive -- verified on live data.
    See docs/research/gap-103-mssql-collation.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        span = table_column_definition_list(clean, m.end())
        if span is None:
            continue  # CREATE TABLE ... AS SELECT, no column-definition list
        open_pos, close_pos = span
        column_list = clean[open_pos + 1 : close_pos]

        for col_match in _PATTERN_RE.finditer(column_list):
            findings.append(
                Finding(
                    detector="mssql_collation",
                    severity="high",
                    object_name=normalize_name(m.group(1)).upper(),
                    line=line_at(clean, open_pos + 1 + col_match.start()),
                    snippet=col_match.group(0),
                    message=_MESSAGE,
                )
            )

    return findings
