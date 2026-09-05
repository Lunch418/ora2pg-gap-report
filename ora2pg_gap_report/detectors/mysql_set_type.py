import re

from .. import mysql_lex
from ..mysql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_SET_RE = re.compile(r"\bSET\s*\(", re.IGNORECASE)

_DOC = """Detect MySQL/MariaDB SET(...) multi-value columns. ora2pg -m maps
them onto plain text, which loads and works but validates nothing --
any string at all becomes storable afterwards. See docs/research/
gap-086-mysql-set-type.md."""

SPEC = DetectorSpec(
    name="mysql_set_type",
    dialect="mysql",
    severity="medium",
    pattern=_SET_RE,
    strategy=TABLE_COLUMNS,
    snippet='SET(...)',
    statement_pattern=_TABLE_RE,
)

find_mysql_set_columns = build(SPEC, mysql_lex)
find_mysql_set_columns.__doc__ = _DOC
