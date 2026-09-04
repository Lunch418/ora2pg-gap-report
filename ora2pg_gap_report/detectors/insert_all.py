import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

# ALL/FIRST are reserved words, so a plain column/table happening to be
# named 'all' or 'first' can't collide here without breaking Oracle's own
# grammar first -- an ordinary INSERT is always 'INSERT INTO ...', never
# 'INSERT ALL'/'INSERT FIRST'. The INTO lookahead is still required as an
# extra guard, since every real multitable INSERT (conditional or not) has
# at least one INTO clause for its first branch.
_INSERT_ALL_RE = re.compile(r"\bINSERT\s+(ALL|FIRST)\b", re.IGNORECASE)
_INTO_RE = re.compile(r"\bINTO\b", re.IGNORECASE)
# Same window size as model_clause.py's MEASURES/RULES lookahead, for the
# same reason: a real WHEN condition ahead of the first INTO can be a
# sizeable compound boolean expression (wide staging tables, generated ETL
# conditions) -- 500 chars was too easy to overrun and silently drop the
# whole finding.
_LOOKAHEAD_WINDOW = 2000


def find_multitable_inserts(source: str) -> list[Finding]:
    """Detect Oracle's multitable INSERT ALL/INSERT FIRST. ora2pg copies
    the construct through unchanged; PostgreSQL has no equivalent syntax
    at all, and PL/pgSQL misparses the first INTO clause as its own
    SELECT-INTO-variable form, failing at function-body compile time. See
    docs/research/gap-016-insert-all.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _INSERT_ALL_RE.finditer(visible):
        window_end = min(len(visible), m.end() + _LOOKAHEAD_WINDOW)
        if not _INTO_RE.search(visible, m.end(), window_end):
            continue

        findings.append(
            Finding(
                detector="insert_all",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=f"INSERT {m.group(1).upper()}",
                message_id="insert_all",
            )
        )

    return findings
