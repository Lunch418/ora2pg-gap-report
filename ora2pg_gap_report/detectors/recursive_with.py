import re

from ..models import Finding
from ..plsql_lex import (
    IDENTIFIER,
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
    skip_balanced_parens,
)

# A CTE declaration not already marked RECURSIVE. The column-list part only
# handles a simple (non-nested) list -- realistic for a CTE's own column
# names, which are never themselves parenthesized expressions.
_WITH_CTE_RE = re.compile(
    rf"\bWITH\s+(?!RECURSIVE\b)({IDENTIFIER})\s*(?:\([^()]*\))?\s*AS\s*\(",
    re.IGNORECASE,
)
_UNION_RE = re.compile(r"\bUNION\b", re.IGNORECASE)

_MESSAGE = (
    "WITH cte AS (...) — рекурсивная факторизация подзапроса Oracle "
    "(recursive subquery factoring), не через CONNECT BY (см. GAP-005 "
    "про этот отдельный случай), а через прямую самоссылку CTE на себя "
    "после UNION [ALL]. Oracle не требует явного ключевого слова "
    "RECURSIVE — рекурсия определяется автоматически по самоссылке. "
    "ora2pg копирует WITH как есть, без добавления RECURSIVE (подтверждено "
    "реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-024-recursive-with.md). PostgreSQL требует "
    "RECURSIVE явно — без него самоссылка на CTE во второй ветке UNION "
    "падает: 'there is a WITH item named ..., but it cannot be referenced "
    "from this part of the query' с подсказкой 'Use WITH RECURSIVE'. Если "
    "запрос дополнительно использует секцию CYCLE, после добавления "
    "RECURSIVE вручную придётся ещё и переставить её после закрывающей "
    "скобки тела CTE и добавить обязательную в PostgreSQL секцию USING — "
    "у Oracle CYCLE стоит перед AS и не требует USING."
)


def find_recursive_with_missing_keyword(source: str) -> list[Finding]:
    """Detect Oracle's native recursive subquery factoring ('WITH cte AS
    (anchor UNION [ALL] recursive-branch-referencing-cte)') missing the
    RECURSIVE keyword PostgreSQL requires. ora2pg passes such a WITH
    clause through unchanged; Oracle doesn't require the keyword (it
    detects recursion by the CTE's self-reference), PostgreSQL does. See
    docs/research/gap-024-recursive-with.md.

    Self-reference detection: not a full parser, so approximated as 'the
    CTE's own name appears again, immediately after FROM/JOIN/a comma (a
    table-reference position), anywhere in the CTE body after its first
    UNION'. Scanning the whole remainder rather than stopping at the
    first UNION/WHERE/nested-subquery keyword handles a recursive branch
    that isn't the second UNION member (more than one non-recursive
    anchor branch before it) and a self-reference reachable only inside a
    nested FROM-clause subquery of its own (whose own WHERE would
    otherwise wrongly look like a boundary). Requiring the immediate
    FROM/JOIN/comma prefix (not just a bare name search) is what rules
    out both the common false-positive shape of an ordinary
    (non-recursive) UNION-based CTE referencing itself nowhere, the
    narrower one of the CTE name coincidentally reappearing as a
    SELECT-list column alias ('SELECT 2 AS tree' -- no FROM/JOIN/comma
    right before it), and a schema-qualified reference to an unrelated
    real table that happens to share the CTE's bare name ('FROM
    archive.tree' -- 'tree' there is preceded by 'archive.', not by
    FROM/JOIN/comma directly)."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _WITH_CTE_RE.finditer(clean):
        cte_name = m.group(1)
        body_start = m.end() - 1  # index of the opening '('
        body_end = skip_balanced_parens(clean, body_start)
        body = clean[body_start:body_end]

        union_match = _UNION_RE.search(body)
        if union_match is None:
            continue

        self_ref_re = re.compile(
            rf"(?:\bFROM\s+|\bJOIN\s+|,\s*){re.escape(cte_name)}\b", re.IGNORECASE
        )
        if not self_ref_re.search(body, union_match.end()):
            continue

        findings.append(
            Finding(
                detector="recursive_with",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=f"WITH {cte_name.upper()} AS (...)",
                message=_MESSAGE,
            )
        )

    return findings
