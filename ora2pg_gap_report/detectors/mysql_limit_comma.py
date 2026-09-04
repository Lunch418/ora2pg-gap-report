import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

# `LIMIT <offset>, <count>`. The two operands are matched as bare words
# rather than digits only, so the same construct written with procedure
# parameters (LIMIT p_offset, p_count -- just as common in stored code)
# is caught too; a plain `LIMIT n` has no comma and never matches.
_LIMIT_COMMA_RE = re.compile(r"\bLIMIT\s+\w+\s*,\s*\w+", re.IGNORECASE)


def find_mysql_limit_comma(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's comma form of LIMIT (`LIMIT offset, count`).
    ora2pg -m copies it through unchanged; PostgreSQL rejects the syntax
    outright, and since bodies are not checked at load time the routine
    fails on its first call. The argument order is reversed relative to
    PostgreSQL's `LIMIT ... OFFSET`. See docs/research/
    gap-075-mysql-limit-comma.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _LIMIT_COMMA_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_limit_comma",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="LIMIT n, m",
                message_id="mysql_limit_comma",
            )
        )

    return findings
