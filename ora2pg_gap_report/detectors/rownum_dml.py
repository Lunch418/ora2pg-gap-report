import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

_ROWNUM_RE = re.compile(r"\bROWNUM\b", re.IGNORECASE)

# Every keyword that can start a statement whose WHERE clause a ROWNUM
# could belong to. Which one is *nearest* in front of the ROWNUM decides
# whether this is the broken shape: ora2pg rewrites `WHERE ROWNUM <= n`
# into `LIMIT n`, which PostgreSQL accepts on a SELECT (including a
# subquery inside an UPDATE/DELETE -- verified separately, that case
# converts and runs correctly) but rejects outright on UPDATE and DELETE,
# which have no LIMIT clause at all.
_STATEMENT_KEYWORD_RE = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|MERGE)\b", re.IGNORECASE)
_BROKEN_IN = frozenset({"UPDATE", "DELETE"})


def _nearest_statement_keyword(
    keywords: list[tuple[int, str]], position: int
) -> str | None:
    """The last statement keyword starting before `position`, or None.

    A single backwards scan over a precomputed list rather than a search
    per ROWNUM: the same shared-index approach the other detectors use
    for enclosing_object_name_index."""
    found = None
    for start, word in keywords:
        if start >= position:
            break
        found = word
    return found


def find_rownum_dml(source: str) -> list[Finding]:
    """Detect Oracle's ROWNUM used directly in an UPDATE or DELETE.
    ora2pg rewrites it into a LIMIT clause, which PostgreSQL does not
    accept on UPDATE/DELETE, so the generated statement fails to parse.
    A ROWNUM whose nearest enclosing statement keyword is SELECT (a
    subquery, even inside an UPDATE/DELETE) is deliberately not flagged:
    that shape converts to a valid subquery LIMIT and runs correctly.
    See docs/research/gap-057-rownum-dml.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    keywords = [
        (m.start(), m.group(1).upper()) for m in _STATEMENT_KEYWORD_RE.finditer(visible)
    ]
    findings: list[Finding] = []

    for m in _ROWNUM_RE.finditer(visible):
        statement = _nearest_statement_keyword(keywords, m.start())
        if statement not in _BROKEN_IN:
            continue
        findings.append(
            Finding(
                detector="rownum_dml",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=f"{statement} ... ROWNUM",
                message_id="rownum_dml",
            )
        )

    return findings
