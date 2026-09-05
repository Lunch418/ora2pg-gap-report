import re

from .. import mysql_lex
from ..mysql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_ENUM_RE = re.compile(r"\bENUM\s*\(", re.IGNORECASE)

_DOC = """Detect MySQL/MariaDB ENUM(...) columns. ora2pg -m synthesizes a
named PostgreSQL enum type for each one but never emits the CREATE
TYPE statement that type needs, so the generated CREATE TABLE
references a type that was never declared and fails to load. See
docs/research/gap-068-mysql-enum-type.md."""

SPEC = DetectorSpec(
    name="mysql_enum_type",
    dialect="mysql",
    severity="high",
    pattern=_ENUM_RE,
    strategy=TABLE_COLUMNS,
    snippet='ENUM(...)',
    table_pattern=_TABLE_RE,
)

find_mysql_enum_columns = build(SPEC, mysql_lex)
find_mysql_enum_columns.__doc__ = _DOC
