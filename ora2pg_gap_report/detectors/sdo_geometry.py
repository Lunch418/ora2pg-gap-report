import re

from .. import plsql_lex
from ..plsql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# SDO_GEOMETRY with or without its MDSYS. schema prefix.
_SDO_GEOMETRY_RE = re.compile(
    r"\b(?:MDSYS\s*\.\s*)?SDO_GEOMETRY\b",
    re.IGNORECASE,
)

_DOC = """Detect Oracle Spatial SDO_GEOMETRY columns. ora2pg maps them onto
PostGIS's `geometry` type but never emits the CREATE EXTENSION postgis
line that type needs, so the generated DDL fails to load on a stock
PostgreSQL. See docs/research/gap-067-sdo-geometry.md."""

SPEC = DetectorSpec(
    name="sdo_geometry",
    dialect="oracle",
    severity="medium",
    pattern=_SDO_GEOMETRY_RE,
    strategy=TABLE_COLUMNS,
    snippet='SDO_GEOMETRY',
    table_pattern=_TABLE_RE,
)

find_sdo_geometry_columns = build(SPEC, plsql_lex)
find_sdo_geometry_columns.__doc__ = _DOC
