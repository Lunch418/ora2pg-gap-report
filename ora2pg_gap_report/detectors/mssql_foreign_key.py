import re

from .. import mssql_lex
from ..mssql_lex import normalize_name, qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_PATTERN_RE = re.compile(r"\bFOREIGN\s+KEY\b", re.IGNORECASE)

_DOC = """Detect T-SQL FOREIGN KEY clauses in a CREATE TABLE column
list. Whenever the target PG_VERSION is left unset or set to 12 or
lower -- ora2pg's own default -- ora2pg -M drops them entirely, on a
file-based scan or a live connection alike, with no error at any stage,
so referential integrity and any ON DELETE cascade silently cease to
exist. Same shared-code mechanism as mysql_foreign_key: a Perl
autovivification accident in Ora2Pg.pm's dialect-agnostic
_create_unique_keys() makes every referenced table look partitioned to
_create_foreign_keys(), which then silently skips the constraint.
Setting PG_VERSION to 13 or higher avoids it. See
docs/research/gap-102-mssql-foreign-key.md."""

SPEC = DetectorSpec(
    name="mssql_foreign_key",
    dialect="mssql",
    severity="high",
    pattern=_PATTERN_RE,
    strategy=TABLE_COLUMNS,
    snippet='FOREIGN KEY',
    statement_pattern=_TABLE_RE,
    normalize_object_name=normalize_name,
)

find_mssql_foreign_keys = build(SPEC, mssql_lex)
find_mssql_foreign_keys.__doc__ = _DOC
