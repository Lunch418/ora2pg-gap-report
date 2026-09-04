import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

# Anchored on the clause's own opening paren: ACCESSIBLE BY is always
# followed by a parenthesised accessor list. Excludes a double-quoted
# identifier literally named "ACCESSIBLE BY" -- mask_strings_and_comments()
# never masks double-quoted identifiers, so the text survives with its
# quotes intact, same guard as index_organized_table.py uses.
_ACCESSIBLE_BY_RE = re.compile(r'(?<!")\bACCESSIBLE\s+BY\s*\(', re.IGNORECASE)


def find_accessible_by(source: str) -> list[Finding]:
    """Detect Oracle's ACCESSIBLE BY whitelist clause on a subprogram.
    ora2pg copies it verbatim into the generated CREATE FUNCTION/PROCEDURE
    header, where PostgreSQL rejects it with a syntax error at load time.
    See docs/research/gap-043-accessible-by.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _ACCESSIBLE_BY_RE.finditer(clean):
        findings.append(
            Finding(
                detector="accessible_by",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="ACCESSIBLE BY",
                message_id="accessible_by",
            )
        )

    return findings
