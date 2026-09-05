import re

from .. import mysql_lex
from ..detector_spec import DetectorSpec, build

# The table *option* AUTO_INCREMENT=<n> (the next value the table will
# hand out), not the column *attribute* AUTO_INCREMENT -- the '=' is what
# separates the two, and the column attribute converts fine (it becomes
# serial), so matching it here would be a false positive on every
# auto-increment table in existence.
_AUTO_INCREMENT_START_RE = re.compile(r"\bAUTO_INCREMENT\s*=\s*(\d+)", re.IGNORECASE)

_DOC = """Detect the MySQL `AUTO_INCREMENT=<n>` *table option*. ora2pg -m
converts the column to serial but drops the starting value, so the
PostgreSQL sequence restarts at 1 and collides with already-migrated
rows on the first insert. The column attribute `AUTO_INCREMENT`
(without `=`) converts correctly and is deliberately not flagged. See
docs/research/gap-080-mysql-auto-increment-start.md."""

SPEC = DetectorSpec(
    name="mysql_auto_increment_start",
    dialect="mysql",
    severity="high",
    pattern=_AUTO_INCREMENT_START_RE,
    snippet=lambda m: f"AUTO_INCREMENT={m.group(1)}",
)

find_mysql_auto_increment_start = build(SPEC, mysql_lex)
find_mysql_auto_increment_start.__doc__ = _DOC
