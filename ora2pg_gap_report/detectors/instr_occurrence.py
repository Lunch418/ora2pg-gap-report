import re

from ..lex_common import call_arguments
from ..models import Finding
from ..plsql_lex import enclosing_object_name, enclosing_object_name_index, line_at, mask_strings_and_comments

_INSTR_RE = re.compile(r"(?<![\w$#.])INSTR\s*\(", re.IGNORECASE)


def find_instr_occurrence(source: str) -> list[Finding]:
    """Detect INSTR with a start position or an occurrence: `INSTR(s, '.',
    -1)`, `INSTR(s, '.', 1, 2)`.

    ora2pg 25.0 rewrites two-argument INSTR as position(sub in s) and
    copies the longer forms, and PostgreSQL 16 has no instr ('function
    instr(text, unknown, integer) does not exist') unless the orafce
    extension is installed -- the routine loads and fails on its first
    call. Oracle 23ai returns 4 for INSTR('a.b.c', '.', -1).
    See docs/research/gap-137-instr-occurrence.md."""
    if "INSTR" not in source.upper():
        return []
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []
    index = None
    for m in _INSTR_RE.finditer(clean):
        args = [" ".join(a.split()) for a in call_arguments(clean, m.end() - 1)]
        if len(args) not in (3, 4):
            continue
        if index is None:
            index = enclosing_object_name_index(clean)
        findings.append(
            Finding(
                detector="instr_occurrence",
                severity="high",
                object_name=enclosing_object_name(index, m.start()),
                line=line_at(clean, m.start()),
                snippet="INSTR(..., ..., " + ", ".join(args[2:]) + ")",
                message_id="instr_occurrence",
            )
        )
    return findings
