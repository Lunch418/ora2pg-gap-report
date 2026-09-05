import re

from .. import mysql_lex
from ..detector_spec import DetectorSpec, build

_ON_DUP_RE = re.compile(r"\bON\s+DUPLICATE\s+KEY\s+UPDATE\b", re.IGNORECASE)

_DOC = """Detect MySQL/MariaDB's `INSERT ... ON DUPLICATE KEY UPDATE`
upsert clause. ora2pg -m copies it through unchanged and PostgreSQL
has no such INSERT syntax at all, so the containing procedure/
function loads cleanly (bodies are not checked) and then fails on
its first call. See docs/research/
gap-070-mysql-on-duplicate-key-update.md."""

SPEC = DetectorSpec(
    name="mysql_on_duplicate_key_update",
    dialect="mysql",
    severity="high",
    pattern=_ON_DUP_RE,
    snippet='ON DUPLICATE KEY UPDATE',
)

find_mysql_on_duplicate_key_update = build(SPEC, mysql_lex)
find_mysql_on_duplicate_key_update.__doc__ = _DOC
