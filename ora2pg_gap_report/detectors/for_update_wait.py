import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

# Oracle's WAIT <n> lock-timeout clause on FOR UPDATE. Anchored on FOR
# UPDATE (with an optional `OF <column list>` in between) rather than on
# the bare word WAIT, which is an ordinary identifier. NOWAIT is
# deliberately not matched: PostgreSQL spells it the same way and ora2pg
# passes it through correctly, so only the numeric-timeout form is a gap.
_FOR_UPDATE_WAIT_RE = re.compile(
    r"\bFOR\s+UPDATE\b(?:\s+OF\b[^;()]*?)?\s+WAIT\s+\d+",
    re.IGNORECASE,
)


def find_for_update_wait(source: str) -> list[Finding]:
    """Detect Oracle's FOR UPDATE ... WAIT n lock-timeout clause. ora2pg
    passes it through unchanged; PostgreSQL supports only NOWAIT and SKIP
    LOCKED there, so the generated query fails to parse. See
    docs/research/gap-056-for-update-wait.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _FOR_UPDATE_WAIT_RE.finditer(visible):
        findings.append(
            Finding(
                detector="for_update_wait",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=" ".join(m.group(0).upper().split()),
                message_id="for_update_wait",
            )
        )

    return findings
