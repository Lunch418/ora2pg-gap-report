from ..models import Finding
from ..mysql_lex import (
    ROUTINE_NAME_RE,
    delimiter_at,
    line_at,
    mask_strings_and_comments,
)


def find_mysql_delimiter_routines(source: str) -> list[Finding]:
    """Detect a MySQL/MariaDB procedure or function written under a
    delimiter other than ';' (DELIMITER ;; / // / $$ ...), which is how
    every routine has to be written for the mysql client, and how
    mysqldump writes every routine it dumps. ora2pg -m ends a routine's
    body at an Oracle-style `END <name>;` and does not know the
    directive, so the closing delimiter, the `DELIMITER ;` line after it
    and whatever else precedes the next routine are copied into the body:
    the generated CREATE PROCEDURE/FUNCTION fails to load, and the file's
    `\\set ON_ERROR_STOP ON` stops the load there. The same routine
    without a DELIMITER loads and runs. See
    docs/research/gap-106-mysql-delimiter-routine.md.

    Routines inside a versioned comment (/*!50003 ... */) are masked out
    here: ora2pg drops those altogether, which is GAP-109's finding."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []
    for m in ROUTINE_NAME_RE.finditer(clean):
        delimiter = delimiter_at(clean, m.start())
        if delimiter == ";":
            continue
        findings.append(
            Finding(
                detector="mysql_delimiter_routine",
                severity="high",
                object_name=m.group(1).upper(),
                line=line_at(clean, m.start()),
                snippet=f"DELIMITER {delimiter}",
                message_id="mysql_delimiter_routine",
            )
        )
    return findings
