import re

from .. import mysql_lex
from ..detector_spec import DetectorSpec, build

_INSERT_IGNORE_RE = re.compile(r"\bINSERT\s+IGNORE\b", re.IGNORECASE)

_DOC = """Detect MySQL/MariaDB's INSERT IGNORE. ora2pg -m copies it through
unchanged; PostgreSQL has no such INSERT syntax, so the containing
routine loads cleanly and fails on its first call. ON CONFLICT DO
NOTHING is narrower than IGNORE, not an exact equivalent. See
docs/research/gap-077-mysql-insert-ignore.md."""

SPEC = DetectorSpec(
    name="mysql_insert_ignore",
    dialect="mysql",
    severity="high",
    pattern=_INSERT_IGNORE_RE,
    snippet='INSERT IGNORE',
)

find_mysql_insert_ignore = build(SPEC, mysql_lex)
find_mysql_insert_ignore.__doc__ = _DOC
