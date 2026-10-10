import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern

_SEQUENCE_RE = re.compile(qualified_name_pattern(r"CREATE\s+SEQUENCE"), re.IGNORECASE)
# START WITH n in Oracle; START n in ora2pg's output, where it worked.
_START_RE = re.compile(r"\bSTART\s+(?:WITH\b|-?\s*\d)", re.IGNORECASE)
_END_RE = re.compile(r";|^\s*/\s*$", re.MULTILINE)


def find_sequence_without_start(source: str) -> list[Finding]:
    """Detect CREATE SEQUENCE without START WITH: `CREATE SEQUENCE s;`,
    `CREATE SEQUENCE s CACHE 100;`.

    Oracle starts such a sequence at its MINVALUE (1). ora2pg 25.0 in file
    mode writes an empty START -- `CREATE SEQUENCE s INCREMENT 1 ... START
    CACHE 100;` -- which PostgreSQL 16 does not parse ('syntax error at or
    near "CACHE"'), and with no option at all it also cuts a trailing digit
    off the name (s2 becomes s). Found in utPLSQL's four sequences.
    --prepare writes the START WITH Oracle implies. See
    docs/research/gap-143-sequence-without-start.md."""
    if "SEQUENCE" not in source.upper():
        return []
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []
    for m in _SEQUENCE_RE.finditer(clean):
        end = _END_RE.search(clean, m.end())
        statement = clean[m.end() : end.start() if end else len(clean)]
        if _START_RE.search(statement):
            continue
        findings.append(
            Finding(
                detector="sequence_without_start",
                severity="high",
                object_name=m.group(1).strip('"').upper(),
                line=line_at(clean, m.start()),
                snippet="CREATE SEQUENCE " + m.group(1),
                message_id="sequence_without_start",
            )
        )
    return findings
