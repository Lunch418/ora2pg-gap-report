import re

from ..lex_common import call_arguments
from ..models import Finding
from ..plsql_lex import enclosing_object_name, enclosing_object_name_index, line_at, mask_strings_and_comments

_SUBSTR_RE = re.compile(r"(?<![\w$#.])SUBSTR\s*\(", re.IGNORECASE)
_ZERO_RE = re.compile(r"0+\Z")
_NEGATIVE_RE = re.compile(r"-\s*\d+\Z")


def find_substr_start(source: str) -> list[Finding]:
    """Detect SUBSTR from position 0 with a length (`SUBSTR(s, 0, 3)`) or
    from a negative position (`SUBSTR(s, -3)`).

    Oracle reads position 0 as 1 and a negative position as counting from
    the end: SUBSTR('abcdef', 0, 3) is 'abc', SUBSTR('abcdef', -3) is
    'def', SUBSTR('abcdef', -3, 2) is 'de'. ora2pg 25.0 copies the call,
    and PostgreSQL's substr counts characters before the first one as
    positions too: 'ab', 'abcdef' and '' -- no error. Checked on a live
    Oracle 23ai and PostgreSQL 16, see docs/research/gap-133-substr-start.md.

    SUBSTR(s, 0) without a length returns the whole string in both and is
    not flagged; a position held in a variable cannot be read here."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []
    index = None
    for m in _SUBSTR_RE.finditer(clean):
        args = [a.strip() for a in call_arguments(clean, m.end() - 1)]
        if len(args) not in (2, 3):
            continue
        start = args[1]
        if _NEGATIVE_RE.match(start):
            snippet = f"SUBSTR(..., {' '.join(start.split()).replace('- ', '-')}{', ...' if len(args) == 3 else ''})"
        elif _ZERO_RE.match(start) and len(args) == 3:
            snippet = "SUBSTR(..., 0, ...)"
        else:
            continue
        if index is None:
            index = enclosing_object_name_index(clean)
        findings.append(
            Finding(
                detector="substr_start",
                severity="high",
                object_name=enclosing_object_name(index, m.start()),
                line=line_at(clean, m.start()),
                snippet=snippet,
                message_id="substr_start",
            )
        )
    return findings
