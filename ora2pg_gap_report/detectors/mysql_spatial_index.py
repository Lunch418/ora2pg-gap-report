import re

from .. import mysql_lex
from ..mysql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_SPATIAL_RE = re.compile(r"\bSPATIAL\s+(?:KEY|INDEX)\b", re.IGNORECASE)

_DOC = """Detect MySQL/MariaDB's inline `SPATIAL KEY`/`SPATIAL INDEX` column-
list clause. ora2pg -m drops the index name and column list and leaves
the bare keywords where a column definition was expected, so CREATE
TABLE fails to load. See docs/research/gap-074-mysql-spatial-index.md."""

SPEC = DetectorSpec(
    name="mysql_spatial_index",
    dialect="mysql",
    severity="high",
    pattern=_SPATIAL_RE,
    strategy=TABLE_COLUMNS,
    snippet=lambda m: m.group(0).upper(),
    statement_pattern=_TABLE_RE,
)

find_mysql_spatial_indexes = build(SPEC, mysql_lex)
find_mysql_spatial_indexes.__doc__ = _DOC
