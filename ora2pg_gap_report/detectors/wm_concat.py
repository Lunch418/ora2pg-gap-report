import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

# Both the bare and the SYS/WMSYS-qualified spellings, since legacy code
# uses all three interchangeably.
_WM_CONCAT_RE = re.compile(
    r"\b(?:(?:SYS|WMSYS)\s*\.\s*)?WM_CONCAT\s*\(",
    re.IGNORECASE,
)


def find_wm_concat(source: str) -> list[Finding]:
    """Detect Oracle's undocumented WM_CONCAT aggregate. ora2pg copies
    the call through unchanged (unlike LISTAGG, which it rewrites to
    string_agg), and PostgreSQL has no such function, so the query fails
    at run time. See docs/research/gap-065-wm-concat.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _WM_CONCAT_RE.finditer(visible):
        findings.append(
            Finding(
                detector="wm_concat",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="WM_CONCAT(",
                message_id="wm_concat",
            )
        )

    return findings
