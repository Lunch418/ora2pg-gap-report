import re

from ..models import Finding
from ..plsql_lex import (
    IDENTIFIER,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
    qualified_name_pattern,
)

_CREATE_TRIGGER_RE = re.compile(
    qualified_name_pattern(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:EDITIONABLE\s+|NONEDITIONABLE\s+)?TRIGGER"
    ),
    re.IGNORECASE,
)
# Where a trigger's header stops and its body begins. FOLLOWS/PRECEDES is
# only legal in the header, so the search is bounded by the first of
# these -- which is what keeps an ordinary identifier named `follows`
# inside the body (or anywhere else in the file) from being matched.
_TRIGGER_BODY_START_RE = re.compile(r"\b(DECLARE|BEGIN|CALL)\b", re.IGNORECASE)
_FOLLOWS_RE = re.compile(
    rf"\b(FOLLOWS|PRECEDES)\s+({IDENTIFIER}(?:\s*\.\s*{IDENTIFIER})?)",
    re.IGNORECASE,
)


def find_trigger_follows(source: str) -> list[Finding]:
    """Detect Oracle's FOLLOWS/PRECEDES trigger-ordering clause. ora2pg
    leaks it into the generated trigger function's body, so the trigger
    loads cleanly and then fails on the first row it fires for. See
    docs/research/gap-053-trigger-follows.md.

    Scoped to the trigger *header* -- from CREATE TRIGGER up to the
    first DECLARE/BEGIN/CALL -- because that is the only place Oracle's
    grammar allows the clause, and both keywords are otherwise perfectly
    ordinary identifiers ('SELECT follows FROM t')."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    findings: list[Finding] = []

    for trigger in _CREATE_TRIGGER_RE.finditer(clean):
        body = _TRIGGER_BODY_START_RE.search(visible, trigger.end())
        header_end = body.start() if body else len(visible)

        for m in _FOLLOWS_RE.finditer(visible, trigger.end(), header_end):
            findings.append(
                Finding(
                    detector="trigger_follows",
                    severity="high",
                    object_name=trigger.group(1).upper(),
                    line=line_at(clean, m.start()),
                    snippet=f"{m.group(1).upper()} {m.group(2).upper()}",
                    message_id="trigger_follows",
                )
            )

    return findings
