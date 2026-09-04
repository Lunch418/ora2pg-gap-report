import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

# All four shapes were confirmed against a real ora2pg 25.0 + PostgreSQL 16
# run (see the research doc); each is copied into the output unchanged.
#   CAST(MULTISET(SELECT ...) AS type)  -- the collect-a-subquery idiom
#   a MULTISET UNION|INTERSECT|EXCEPT b -- collection set operators
#   x MEMBER OF coll                    -- membership test
#   a SUBMULTISET OF b                  -- subset test
# `MEMBER` alone is deliberately not matched: `MEMBER FUNCTION` /
# `MEMBER PROCEDURE` are ordinary object-type method declarations that
# have nothing to do with collection membership, and requiring the
# following `OF` keeps them out.
_MULTISET_RE = re.compile(
    r"\bCAST\s*\(\s*MULTISET\s*\("
    r"|\bMULTISET\s+(?:UNION|INTERSECT|EXCEPT)\b"
    r"|\bMEMBER\s+OF\b"
    r"|\bSUBMULTISET\s+OF\b",
    re.IGNORECASE,
)


def find_multiset_operators(source: str) -> list[Finding]:
    """Detect Oracle's collection operators: CAST(MULTISET(...)),
    MULTISET UNION/INTERSECT/EXCEPT, MEMBER OF, SUBMULTISET OF. ora2pg
    copies all of them through unchanged; PostgreSQL has none of them, so
    the generated code fails to load. See
    docs/research/gap-041-multiset-operator.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _MULTISET_RE.finditer(visible):
        snippet = " ".join(m.group(0).upper().split())
        findings.append(
            Finding(
                detector="multiset_operator",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=snippet,
                message_id="multiset_operator",
            )
        )

    return findings
