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
_PATTERN_RE = re.compile(r"\bROWVERSION\b", re.IGNORECASE)

_MESSAGE = (
    "ROWVERSION — столбец SQL Server, значение которого сервер сам "
    "меняет при каждом изменении строки; на нём обычно построена "
    "оптимистичная блокировка (UPDATE ... WHERE rv = <прочитанное "
    "значение>). ora2pg (-M) отображает его в обычный bytea "
    "(подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-105-mssql-rowversion.md). Тип по размеру подходит, "
    "но главного — самообновления — у bytea нет: после миграции значение "
    "не меняется никогда. Ошибки не будет ни на одном этапе, и это самое "
    "опасное: проверка WHERE rv = <старое значение> теперь совпадает "
    "всегда, то есть конфликт одновременных правок перестаёт "
    "обнаруживаться и правки молча затирают друг друга. Восстанавливается "
    "триггером BEFORE UPDATE, увеличивающим счётчик версии, либо "
    "переходом на xmin — системный столбец PostgreSQL, который меняется "
    "при каждом обновлении строки сам. Отдельно проверьте столбцы типа "
    "timestamp: в T-SQL это устаревший синоним ROWVERSION, и этот "
    "детектор его намеренно не помечает, чтобы не путать со столбцом, "
    "который просто называется timestamp."
)


def find_mssql_rowversion_columns(source: str) -> list[Finding]:
    """Detect T-SQL ROWVERSION columns. ora2pg -M maps them onto a
    plain bytea, which never changes on its own, so optimistic-locking
    checks built on the column silently stop detecting conflicts. See
    docs/research/gap-105-mssql-rowversion.md."""
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
                    detector="mssql_rowversion",
                    severity="high",
                    object_name=normalize_name(m.group(1)).upper(),
                    line=line_at(clean, open_pos + 1 + col_match.start()),
                    snippet="ROWVERSION",
                    message=_MESSAGE,
                )
            )

    return findings
