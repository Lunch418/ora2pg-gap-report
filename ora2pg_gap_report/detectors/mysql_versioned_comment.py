import re

from ..models import Finding
from ..mysql_lex import line_at, mask_comments_only

# One MySQL executable ("versioned") comment: /*!NNNNN ... */, or MariaDB's
# /*M!NNNNNN ... */. MySQL runs the contents when its own version is at
# least NNNNN, so for MySQL they are code, not commentary.
_VERSIONED_COMMENT_RE = re.compile(r"/\*M?!\d*(.*?)\*/", re.DOTALL)
# mysqldump splits one CREATE across several consecutive comments --
# /*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER
# `name` ...*/ -- so the object is read from their joined contents.
_OBJECT_RE = re.compile(
    r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?(?:ALGORITHM\s*=\s*\w+\s+)?(?:DEFINER\s*=\s*\S+\s+)?"
    r"(?:SQL\s+SECURITY\s+\w+\s+)?(TRIGGER|VIEW|PROCEDURE|FUNCTION)\s+"
    r"(?:`?[A-Za-z0-9_$]+`?\.)?`?([A-Za-z0-9_$]+)`?",
    re.IGNORECASE,
)


def find_mysql_versioned_comments(source: str) -> list[Finding]:
    """Detect a trigger, view, procedure or function wrapped in MySQL's
    executable comments -- mysqldump's own output for every trigger and
    view, and for routines in older versions. MySQL executes them; ora2pg
    -m removes comments before it parses, so the whole object is gone:
    no output, no error, not even a log line. See
    docs/research/gap-109-mysql-versioned-comment.md.

    Searches the raw source, since what it looks for is itself a comment.
    A match only counts where the comments-only view blanks it too --
    i.e. where it really is a comment, not text inside a string."""
    comments_blanked = mask_comments_only(source)
    runs: list[tuple[int, list[str]]] = []
    run_end = -1
    for m in _VERSIONED_COMMENT_RE.finditer(source):
        if comments_blanked[m.start()] != " ":
            continue  # inside a string literal, not a comment
        if runs and source[run_end : m.start()].strip() == "":
            runs[-1][1].append(m.group(1))
        else:
            runs.append((m.start(), [m.group(1)]))
        run_end = m.end()
    findings: list[Finding] = []
    for start, bodies in runs:
        created = _OBJECT_RE.match(" ".join(bodies))
        if created is None:
            continue  # SET @saved_..., DROP ... IF EXISTS and the like
        kind = created.group(1).upper()
        findings.append(
            Finding(
                detector="mysql_versioned_comment",
                severity="high",
                object_name=created.group(2).upper(),
                line=line_at(source, start),
                snippet=f"/*!... CREATE {kind} ... */",
                message_id="mysql_versioned_comment",
            )
        )
    return findings
