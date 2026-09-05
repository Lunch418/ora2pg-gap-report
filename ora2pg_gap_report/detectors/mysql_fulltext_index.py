import re

from .. import mysql_lex
from ..mysql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_FULLTEXT_RE = re.compile(r"\bFULLTEXT\s+(?:KEY|INDEX)\b", re.IGNORECASE)

_DOC = """Detect MySQL/MariaDB's inline `FULLTEXT KEY`/`FULLTEXT INDEX`
column-list clause. ora2pg -m doesn't recognize it as an index at
all: the index name and column list are dropped, and the bare
keywords are left sitting where a column definition was expected,
which PostgreSQL then tries (and fails) to parse as one. See
docs/research/gap-072-mysql-fulltext-index.md."""

SPEC = DetectorSpec(
    name="mysql_fulltext_index",
    dialect="mysql",
    severity="high",
    pattern=_FULLTEXT_RE,
    strategy=TABLE_COLUMNS,
    snippet=lambda m: m.group(0).upper(),
    statement_pattern=_TABLE_RE,
)

find_mysql_fulltext_indexes = build(SPEC, mysql_lex)
find_mysql_fulltext_indexes.__doc__ = _DOC
