from ..models import Finding
from ..mysql_lex import (
    TRIGGER_NAME_RE,
    delimiter_at,
    line_at,
    mask_strings_and_comments,
)


def find_mysql_delimiter_triggers(source: str) -> list[Finding]:
    """Detect a MySQL/MariaDB trigger written under a delimiter with no
    ';' in it (DELIMITER // / $$ / | ...). ora2pg -m's trigger parser
    only finds the end of a trigger by a ';', so under such a delimiter
    it finds no trigger at all: nothing is generated, nothing is
    reported, and the table simply has no trigger in PostgreSQL. Under
    DELIMITER ;; -- mysqldump's own choice -- the trigger converts, which
    is why that one is not flagged. See
    docs/research/gap-107-mysql-delimiter-trigger.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []
    for m in TRIGGER_NAME_RE.finditer(clean):
        delimiter = delimiter_at(clean, m.start())
        if ";" in delimiter:
            continue
        findings.append(
            Finding(
                detector="mysql_delimiter_trigger",
                severity="high",
                object_name=m.group(1).upper(),
                line=line_at(clean, m.start()),
                snippet=f"DELIMITER {delimiter}",
                message_id="mysql_delimiter_trigger",
            )
        )
    return findings
