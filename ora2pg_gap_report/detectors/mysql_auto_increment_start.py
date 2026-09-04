import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

# The table *option* AUTO_INCREMENT=<n> (the next value the table will
# hand out), not the column *attribute* AUTO_INCREMENT -- the '=' is what
# separates the two, and the column attribute converts fine (it becomes
# serial), so matching it here would be a false positive on every
# auto-increment table in existence.
_AUTO_INCREMENT_START_RE = re.compile(r"\bAUTO_INCREMENT\s*=\s*(\d+)", re.IGNORECASE)


def find_mysql_auto_increment_start(source: str) -> list[Finding]:
    """Detect the MySQL `AUTO_INCREMENT=<n>` *table option*. ora2pg -m
    converts the column to serial but drops the starting value, so the
    PostgreSQL sequence restarts at 1 and collides with already-migrated
    rows on the first insert. The column attribute `AUTO_INCREMENT`
    (without `=`) converts correctly and is deliberately not flagged. See
    docs/research/gap-080-mysql-auto-increment-start.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _AUTO_INCREMENT_START_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_auto_increment_start",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=f"AUTO_INCREMENT={m.group(1)}",
                message_id="mysql_auto_increment_start",
            )
        )

    return findings
