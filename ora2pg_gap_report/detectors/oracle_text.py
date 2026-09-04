import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
    qualified_name_pattern,
    skip_balanced_parens,
    statement_end,
)

_INDEX_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+INDEX"),
    re.IGNORECASE,
)
_INDEXTYPE_RE = re.compile(r"\bINDEXTYPE\s+IS\s+CTXSYS\.(CONTEXT|CTXCAT|CTXRULE)\b", re.IGNORECASE)
# CONTAINS/CATSEARCH/MATCHES are plausible names for an unrelated
# user-defined function (a collection-membership helper named "contains"
# is entirely ordinary Oracle code) -- unlike the domain-index check
# above, which has no realistic collision risk at all. Oracle Text's
# functions always return a relevance score and are, in every real usage,
# immediately compared against a numeric threshold or bind variable right
# after the call ('CONTAINS(text, 'dog') > 0') -- requiring that
# comparison is what disambiguates a real Oracle Text call from a
# same-named function returning something else entirely.
_TEXT_FUNCTION_RE = re.compile(r"\b(CONTAINS|CATSEARCH|MATCHES)\s*\(", re.IGNORECASE)
_SCORE_COMPARISON_RE = re.compile(r"\s*(?:>=|<=|<>|!=|>|<|=)\s*(?:\d|:)")


def find_oracle_text_usage(source: str) -> list[Finding]:
    """Detect Oracle Text: CREATE INDEX ... INDEXTYPE IS CTXSYS.* domain
    indexes and CONTAINS()/CATSEARCH()/MATCHES() function calls. ora2pg
    silently drops the INDEXTYPE clause (index becomes an ordinary
    B-tree, no full-text search capability at all) and passes the search
    functions through unchanged, which don't exist in PostgreSQL. See
    docs/research/gap-023-oracle-text.md.

    The function-call check additionally requires an immediate numeric/
    bind-variable comparison right after the call ('CONTAINS(...) > 0')
    -- see _SCORE_COMPARISON_RE's comment for why.

    The index check's statement scoping uses statement_end() -- up to the
    next ';', or the start of the next CREATE INDEX if there's no ';'
    (DBMS_METADATA.GET_DDL's default output has none) -- not just "next
    ';' or end of file", which would otherwise misattribute a later
    index's own INDEXTYPE to an earlier, unterminated one. The reported
    line is the actual INDEXTYPE token's line, not the statement's
    opening CREATE INDEX line -- same reasoning as
    invisible_index.py/read_only_table.py for real indexes being
    multi-line."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    # CREATE INDEX ... INDEXTYPE is schema-level DDL, not dynamic-SQL-aware
    # here -- same scope as the other schema-level detectors (table
    # partitioning, external tables, etc.), which a dynamic CREATE INDEX
    # is out of scope for in this pass. Only the CONTAINS/CATSEARCH/MATCHES
    # function-call check below uses the visible view.
    index_matches = list(_INDEX_RE.finditer(clean))
    for i, m in enumerate(index_matches):
        next_start = index_matches[i + 1].start() if i + 1 < len(index_matches) else None
        stmt_end = statement_end(clean, m.end(), next_start)
        statement = clean[m.end() : stmt_end]
        it_match = _INDEXTYPE_RE.search(statement)
        if it_match is None:
            continue
        findings.append(
            Finding(
                detector="oracle_text",
                severity="high",
                object_name=m.group(1).upper(),
                line=line_at(clean, m.end() + it_match.start()),
                snippet=f"INDEXTYPE IS CTXSYS.{it_match.group(1).upper()}",
                message_id="oracle_text",
            )
        )

    for m in _TEXT_FUNCTION_RE.finditer(visible):
        call_end = skip_balanced_parens(visible, m.end() - 1)
        if not _SCORE_COMPARISON_RE.match(visible, call_end):
            continue
        findings.append(
            Finding(
                detector="oracle_text",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(visible, m.start()),
                snippet=f"{m.group(1).upper()}(...)",
                message_id="oracle_text",
            )
        )

    return findings
