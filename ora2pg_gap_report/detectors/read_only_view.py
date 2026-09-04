import re

from ..models import Finding
from ..plsql_lex import (
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
    qualified_name_pattern,
    statement_end,
)

_CREATE_VIEW_RE = re.compile(
    qualified_name_pattern(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:NO\s+)?(?:FORCE\s+)?"
        r"(?:EDITIONABLE\s+|NONEDITIONABLE\s+)?VIEW"
    ),
    re.IGNORECASE,
)
_WITH_READ_ONLY_RE = re.compile(r"\bWITH\s+READ\s+ONLY\b", re.IGNORECASE)


def find_read_only_views(source: str) -> list[Finding]:
    """Detect Oracle's CREATE VIEW ... WITH READ ONLY. ora2pg drops the
    clause, and the resulting PostgreSQL view is auto-updatable, so
    writes that Oracle rejected now silently succeed. See
    docs/research/gap-066-read-only-view.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    starts = [m for m in _CREATE_VIEW_RE.finditer(clean)]
    findings: list[Finding] = []

    for i, m in enumerate(starts):
        next_start = starts[i + 1].start() if i + 1 < len(starts) else None
        end = statement_end(clean, m.end(), next_start)

        clause = _WITH_READ_ONLY_RE.search(visible, m.end(), end)
        if clause is None:
            continue
        findings.append(
            Finding(
                detector="read_only_view",
                severity="high",
                object_name=m.group(1).upper(),
                line=line_at(clean, clause.start()),
                snippet="WITH READ ONLY",
                message_id="read_only_view",
            )
        )

    return findings
