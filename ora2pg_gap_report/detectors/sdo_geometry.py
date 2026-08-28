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
# SDO_GEOMETRY with or without its MDSYS. schema prefix.
_SDO_GEOMETRY_RE = re.compile(
    r"\b(?:MDSYS\s*\.\s*)?SDO_GEOMETRY\b",
    re.IGNORECASE,
)

_MESSAGE = (
    "SDO_GEOMETRY — пространственный тип Oracle Spatial. ora2pg "
    "конвертирует его в geometry(GEOMETRY) — то есть в тип расширения "
    "PostGIS, — но саму строку CREATE EXTENSION postgis в вывод не "
    "добавляет (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL "
    "16, docs/research/gap-067-sdo-geometry.md). На чистой PostgreSQL без "
    "предварительно установленного PostGIS DDL падает на загрузке с "
    "'type \"geometry\" does not exist'. Само по себе отображение выбрано "
    "верно, поэтому severity здесь medium, а не high: чинится это одной "
    "строкой CREATE EXTENSION postgis перед загрузкой схемы. Заметить "
    "стоит другое — в том же прогоне для SYS_GUID() ora2pg строку "
    "CREATE EXTENSION \"uuid-ossp\" выводит сам, так что рассчитывать на "
    "автоматическое подключение нужного расширения нельзя. Отдельно "
    "проверьте перенос самих значений: модель координат и семантика "
    "SDO_GEOMETRY и PostGIS совпадают не полностью."
)


def find_sdo_geometry_columns(source: str) -> list[Finding]:
    """Detect Oracle Spatial SDO_GEOMETRY columns. ora2pg maps them onto
    PostGIS's `geometry` type but never emits the CREATE EXTENSION postgis
    line that type needs, so the generated DDL fails to load on a stock
    PostgreSQL. See docs/research/gap-067-sdo-geometry.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        span = table_column_definition_list(clean, m.end())
        if span is None:
            continue  # bare CTAS with no column-definition list at all
        open_pos, close_pos = span
        column_list = clean[open_pos + 1 : close_pos]

        for col_match in _SDO_GEOMETRY_RE.finditer(column_list):
            findings.append(
                Finding(
                    detector="sdo_geometry",
                    severity="medium",
                    object_name=m.group(1).upper(),
                    line=line_at(clean, open_pos + 1 + col_match.start()),
                    snippet="SDO_GEOMETRY",
                    message=_MESSAGE,
                )
            )

    return findings
