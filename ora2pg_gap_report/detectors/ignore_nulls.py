import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

# Both spellings of Oracle's null-treatment clause on analytic functions.
# RESPECT NULLS is Oracle's default and therefore usually implicit, but it
# is legal to write it out, and when it is written out ora2pg copies it
# through exactly like IGNORE NULLS -- confirmed by a separate probe, so
# both are flagged rather than just the interesting one.
_NULL_TREATMENT_RE = re.compile(r"\b(?:IGNORE|RESPECT)\s+NULLS\b", re.IGNORECASE)


def find_ignore_nulls(source: str) -> list[Finding]:
    """Detect Oracle's IGNORE NULLS / RESPECT NULLS clause on analytic
    functions. ora2pg passes it through unchanged and PostgreSQL 16 has
    no equivalent syntax, so the generated query fails to parse. See
    docs/research/gap-048-ignore-nulls.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _NULL_TREATMENT_RE.finditer(visible):
        findings.append(
            Finding(
                detector="ignore_nulls",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=" ".join(m.group(0).upper().split()),
                message_id="ignore_nulls",
            )
        )

    return findings
