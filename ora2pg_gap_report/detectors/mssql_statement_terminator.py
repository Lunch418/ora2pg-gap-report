import re

from ..models import Finding
from ..mssql_lex import mask_strings_and_comments
from ..plsql_lex import line_at

_GO_LINE_RE = re.compile(r"^[ \t]*GO(?:[ \t]+\d+)?[ \t]*;?[ \t\r]*$", re.IGNORECASE | re.MULTILINE)
_ROUTINE_RE = re.compile(r"\bCREATE\s+(?:OR\s+(?:ALTER|REPLACE)\s+)?(?:PROCEDURE|PROC|FUNCTION|TRIGGER)\b", re.IGNORECASE)
_STATEMENT_HEAD_RE = re.compile(r"\S[^\n]*")
_TABLE_LINE_RE = re.compile(r"^CREATE\s+TABLE\b", re.IGNORECASE | re.MULTILINE)


def find_mssql_statement_terminator(source: str) -> list[Finding]:
    """Detect T-SQL statements ended by GO alone, without `;` -- `CREATE
    TABLE actor (...)` then `GO`, the way SSMS scripts them -- or by
    nothing at all before the next CREATE TABLE.

    ora2pg 25.0 (-M) needs the `;`: it converts the first such statement
    and drops everything after it up to the next `;` -- tables, indexes,
    ALTERs -- without a word. On jOOQ's Sakila for SQL Server, 1 table of
    16 came out. --prepare ends each batch with `;` (and drops the GO),
    and all of them convert. A routine's GO is GAP-126's. See
    docs/research/gap-149-mssql-statement-terminator.md.

    Reported once per file, at the first such statement, with how many
    there are: the cause and the fix are one."""
    if "GO" not in source.upper() and "CREATE" not in source.upper():
        return []
    clean = mask_strings_and_comments(source)
    unterminated: list[int] = []
    batch_start = 0
    # A batch ends at GO, and also at a CREATE TABLE starting a line.
    ends = sorted(
        [(go.start(), go.end()) for go in _GO_LINE_RE.finditer(clean)]
        + [(t.start(), t.start()) for t in _TABLE_LINE_RE.finditer(clean) if t.start() > 0]
    )
    for end_start, end_end in ends:
        batch = clean[batch_start:end_start]
        code = batch.rstrip()
        if code.strip() and not code.endswith(";") and not _ROUTINE_RE.search(batch):
            # The batch's last statement: what follows its last `;`.
            last = code.rfind(";") + 1
            head = _STATEMENT_HEAD_RE.search(batch, last)
            unterminated.append(batch_start + (head.start() if head else last))
        batch_start = end_end
    if not unterminated:
        return []
    first = unterminated[0]
    head = _STATEMENT_HEAD_RE.match(clean, first)
    text = " ".join(source[first : head.end() if head else first + 40].split())[:50]
    return [
        Finding(
            detector="mssql_statement_terminator",
            severity="high",
            object_name="UNKNOWN",
            line=line_at(clean, first),
            snippet=f"{text} (no ; at its end, {len(unterminated)} statements)",
            message_id="mssql_statement_terminator",
        )
    ]
