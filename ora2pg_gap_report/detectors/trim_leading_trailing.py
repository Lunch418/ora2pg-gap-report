import re

from ..models import Finding
from ..plsql_lex import enclosing_object_name, enclosing_object_name_index, line_at, mask_strings_and_comments

# TRIM(LEADING x FROM y); the second form is ora2pg's output, so --load-check
# can tie its error here.
_TRIM_RE = re.compile(r"(?<![\w$#.])TRIM\s*\(\s*(?:BOTH\s+)?(LEADING|TRAILING)\b", re.IGNORECASE)


def find_trim_leading_trailing(source: str) -> list[Finding]:
    """Detect TRIM(LEADING x FROM y) and TRIM(TRAILING x FROM y).

    PostgreSQL has the very same syntax, but ora2pg 25.0 puts a BOTH in
    front of every TRIM it sees: trim(both leading x from y), which
    PostgreSQL 16 does not parse ('syntax error at or near "leading"') --
    the routine does not load. TRIM(BOTH ...) and TRIM(x) come out right.
    Found in utPLSQL (ut_utils). --fix removes the extra BOTH. See
    docs/research/gap-145-trim-leading-trailing.md."""
    if "TRIM" not in source.upper():
        return []
    clean = mask_strings_and_comments(source)
    index = None
    findings: list[Finding] = []
    for m in _TRIM_RE.finditer(clean):
        if index is None:
            index = enclosing_object_name_index(clean)
        findings.append(
            Finding(
                detector="trim_leading_trailing",
                severity="high",
                object_name=enclosing_object_name(index, m.start()),
                line=line_at(clean, m.start()),
                snippet=f"TRIM({m.group(1).upper()} ... FROM ...)",
                message_id="trim_leading_trailing",
            )
        )
    return findings
