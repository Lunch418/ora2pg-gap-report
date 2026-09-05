import re

from .. import mysql_lex
from ..detector_spec import DetectorSpec, build

_LAST_INSERT_ID_RE = re.compile(r"\bLAST_INSERT_ID\s*\(", re.IGNORECASE)

_DOC = """Detect MySQL/MariaDB's LAST_INSERT_ID() function. ora2pg -m copies
the call through unchanged and PostgreSQL has no such function, so
the containing routine loads cleanly and fails on its first call.
See docs/research/gap-079-mysql-last-insert-id.md."""

SPEC = DetectorSpec(
    name="mysql_last_insert_id",
    dialect="mysql",
    severity="high",
    pattern=_LAST_INSERT_ID_RE,
    snippet='LAST_INSERT_ID()',
)

find_mysql_last_insert_id = build(SPEC, mysql_lex)
find_mysql_last_insert_id.__doc__ = _DOC
