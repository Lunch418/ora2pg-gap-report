import re

from ..models import Finding
from ..plsql_lex import (
    IDENTIFIER,
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

# GOTO followed by a label name. The label name is required by the match
# so that the word alone -- as a column, a variable or part of an
# identifier -- is not enough to produce a finding.
_GOTO_RE = re.compile(rf"\bGOTO\s+({IDENTIFIER})", re.IGNORECASE)


def find_goto_statements(source: str) -> list[Finding]:
    """Detect PL/SQL GOTO statements. ora2pg copies them through
    unchanged and PL/pgSQL has no GOTO at all, so the procedure loads
    cleanly (bodies are not checked) and then fails on its first call.
    See docs/research/gap-063-goto-statement.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _GOTO_RE.finditer(visible):
        findings.append(
            Finding(
                detector="goto_statement",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=f"GOTO {m.group(1).lower()}",
                message_id="goto_statement",
            )
        )

    return findings
