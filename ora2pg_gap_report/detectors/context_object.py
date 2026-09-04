import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern

_CONTEXT_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+(?:OR\s+REPLACE\s+)?CONTEXT"),
    re.IGNORECASE,
)


def find_context_declarations(source: str) -> list[Finding]:
    """Detect Oracle CREATE CONTEXT declarations. ora2pg has no
    conversion path for these at all -- see
    docs/research/gap-015-context.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _CONTEXT_RE.finditer(clean):
        findings.append(
            Finding(
                detector="context_object",
                severity="medium",
                object_name=m.group(1).upper(),
                line=line_at(clean, m.start()),
                snippet="CREATE CONTEXT",
                message_id="context_object",
            )
        )

    return findings
