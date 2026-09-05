import re

from .. import mysql_lex
from ..mysql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_FOREIGN_KEY_RE = re.compile(r"\bFOREIGN\s+KEY\b", re.IGNORECASE)

_DOC = """Detect MySQL/MariaDB FOREIGN KEY clauses inside a CREATE TABLE
column list. ora2pg -m drops them entirely -- no FOREIGN KEY appears
anywhere in its output, and it has no separate foreign-key export
type -- so referential integrity silently disappears with no error at
any stage. See docs/research/gap-082-mysql-foreign-key.md."""

SPEC = DetectorSpec(
    name="mysql_foreign_key",
    dialect="mysql",
    severity="high",
    pattern=_FOREIGN_KEY_RE,
    strategy=TABLE_COLUMNS,
    snippet='FOREIGN KEY',
    statement_pattern=_TABLE_RE,
)

find_mysql_foreign_keys = build(SPEC, mysql_lex)
find_mysql_foreign_keys.__doc__ = _DOC
