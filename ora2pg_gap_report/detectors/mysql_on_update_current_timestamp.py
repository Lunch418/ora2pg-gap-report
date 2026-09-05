import re

from .. import mysql_lex
from ..mysql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_ON_UPDATE_RE = re.compile(r"\bON\s+UPDATE\s+CURRENT_TIMESTAMP\b", re.IGNORECASE)

_DOC = """Detect MySQL/MariaDB's `DEFAULT CURRENT_TIMESTAMP ON UPDATE
CURRENT_TIMESTAMP` column clause. ora2pg -m copies the `ON UPDATE
CURRENT_TIMESTAMP` fragment verbatim into the generated DEFAULT,
which is not valid PostgreSQL syntax at all -- CREATE TABLE fails to
load immediately. See docs/research/
gap-069-mysql-on-update-current-timestamp.md."""

SPEC = DetectorSpec(
    name="mysql_on_update_current_timestamp",
    dialect="mysql",
    severity="high",
    pattern=_ON_UPDATE_RE,
    strategy=TABLE_COLUMNS,
    snippet='ON UPDATE CURRENT_TIMESTAMP',
    statement_pattern=_TABLE_RE,
)

find_mysql_on_update_current_timestamp = build(SPEC, mysql_lex)
find_mysql_on_update_current_timestamp.__doc__ = _DOC
