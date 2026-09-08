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
column list. Whenever the target PG_VERSION is left unset or set to 12
or lower -- ora2pg's own default when nobody has edited the config yet --
no FOREIGN KEY appears anywhere in ora2pg's output, on a file-based scan
(-i <file>) or a live database connection alike: a Perl autovivification
accident in Ora2Pg.pm's shared, dialect-agnostic _create_unique_keys()
makes every referenced table look partitioned to _create_foreign_keys(),
which then silently skips the constraint. Setting PG_VERSION to 13 or
higher avoids it; referential integrity otherwise disappears with no
error at any stage. Two earlier explanations for this finding (no -t
export type for foreign keys; a file-based-path-only, live-catalog-only
limitation) were each wrong and have been corrected in turn.
See docs/research/gap-082-mysql-foreign-key.md."""

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
