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
                    message_id="sdo_geometry",
                )
            )

    return findings
