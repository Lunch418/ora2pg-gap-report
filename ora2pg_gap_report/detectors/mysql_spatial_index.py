import re

from ..models import Finding
from ..mysql_lex import (
    line_at,
    mask_strings_and_comments,
    qualified_name_pattern,
    table_column_definition_list,
)

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_SPATIAL_RE = re.compile(r"\bSPATIAL\s+(?:KEY|INDEX)\b", re.IGNORECASE)

_MESSAGE = (
    "SPATIAL KEY/INDEX — пространственный индекс MySQL/MariaDB, "
    "объявленный в списке столбцов CREATE TABLE. ora2pg (-m) не "
    "распознаёт конструкцию как индекс: имя индекса и список столбцов "
    "теряются, а слова 'spatial KEY' остаются в выводе на месте, где "
    "ожидалось очередное определение столбца — подтверждено реальным "
    "прогоном ora2pg 25.0 + PostgreSQL 16 (docs/research/"
    "gap-074-mysql-spatial-index.md). CREATE TABLE падает немедленно, при "
    "загрузке схемы: 'type \"key\" does not exist'. Отличается от "
    "родственного GAP-072 (FULLTEXT) не только ключевым словом, но и "
    "починкой: пространственный индекс восстанавливается как CREATE "
    "INDEX ... USING gist (<столбец>) поверх PostGIS-типа, и отдельно "
    "нужно проверить сам тип столбца — MySQL-овские POINT/GEOMETRY "
    "переносятся не всегда так, как ожидается."
)


def find_mysql_spatial_indexes(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's inline `SPATIAL KEY`/`SPATIAL INDEX` column-
    list clause. ora2pg -m drops the index name and column list and leaves
    the bare keywords where a column definition was expected, so CREATE
    TABLE fails to load. See docs/research/gap-074-mysql-spatial-index.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        span = table_column_definition_list(clean, m.end())
        if span is None:
            continue  # bare CTAS with no column-definition list at all
        open_pos, close_pos = span
        column_list = clean[open_pos + 1 : close_pos]

        for col_match in _SPATIAL_RE.finditer(column_list):
            findings.append(
                Finding(
                    detector="mysql_spatial_index",
                    severity="high",
                    object_name=m.group(1).upper(),
                    line=line_at(clean, open_pos + 1 + col_match.start()),
                    snippet=col_match.group(0).upper(),
                    message=_MESSAGE,
                )
            )

    return findings
