import re

from ..models import Finding
from ..plsql_lex import (
    IDENTIFIER,
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
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
# A later CTE in the same WITH list, right after the previous CTE's closing
# ')' -- 'WITH seed AS (...), tree AS (...)' is the common real-world shape
# (a non-recursive anchor/seed CTE listed before the recursive one), and
# _WITH_CTE_RE alone only ever matches the first CTE (it requires a literal
# WITH immediately before the name). Matched with .match(pos) (anchored,
# not .search()) so it only fires immediately after the prior body's ')' --
# anything else there means the WITH list has ended.
_NEXT_CTE_RE = re.compile(
    rf"\s*,\s*({IDENTIFIER})\s*(?:\([^()]*\))?\s*AS\s*\(",
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
    FROM/JOIN/comma directly).

    A WITH clause can list more than one CTE ('WITH seed AS (...), tree
    AS (...)' -- a non-recursive anchor CTE listed before the recursive
    one is a common real-world shape). _WITH_CTE_RE only ever matches the
    first, since it requires a literal WITH right before the name; every
    later one is picked up by _NEXT_CTE_RE immediately after the previous
    CTE's own closing ')', each checked for self-reference independently."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _WITH_CTE_RE.finditer(visible):
        # (name, name_start, body_start) for every CTE in this WITH list --
        # the first one from _WITH_CTE_RE itself, then every following
        # ', name AS (' picked up right after the previous one's ')'.
        ctes = [(m.group(1), m.start(), m.end() - 1)]
        pos = skip_balanced_parens(visible, ctes[0][2])
        while True:
            next_m = _NEXT_CTE_RE.match(visible, pos)
            if next_m is None:
                break
            next_body_start = next_m.end() - 1
            ctes.append((next_m.group(1), next_m.start(), next_body_start))
            pos = skip_balanced_parens(visible, next_body_start)

        for cte_name, name_start, body_start in ctes:
            body_end = skip_balanced_parens(visible, body_start)
            body = visible[body_start:body_end]

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
                    object_name=enclosing_object_name(name_index, name_start),
                    line=line_at(clean, name_start),
                    snippet=f"WITH {cte_name.upper()} AS (...)",
                    message=_MESSAGE,
                )
            )

    return findings
