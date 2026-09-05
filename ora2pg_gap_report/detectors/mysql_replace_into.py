import re

from .. import mysql_lex
from ..detector_spec import DetectorSpec, build

# `INTO` is required by the match so the ordinary REPLACE(str, from, to)
# string function -- an entirely different thing, and one ora2pg handles
# fine -- can't produce a finding.
_REPLACE_INTO_RE = re.compile(r"\bREPLACE\s+INTO\b", re.IGNORECASE)

_DOC = """Detect MySQL/MariaDB's REPLACE INTO statement. ora2pg -m copies it
through unchanged and PostgreSQL has no such statement, so the
containing routine loads cleanly and fails on its first call. Note
that ON CONFLICT DO UPDATE is not an exact equivalent -- REPLACE
deletes and re-inserts, which fires delete-side triggers/cascades.
See docs/research/gap-076-mysql-replace-into.md."""

SPEC = DetectorSpec(
    name="mysql_replace_into",
    dialect="mysql",
    severity="high",
    pattern=_REPLACE_INTO_RE,
    snippet='REPLACE INTO',
)

find_mysql_replace_into = build(SPEC, mysql_lex)
find_mysql_replace_into.__doc__ = _DOC
