import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

# CONNECT_BY_ROOT is an operator (prefix, applied to an expression),
# CONNECT_BY_ISLEAF/CONNECT_BY_ISCYCLE are pseudocolumns -- all three are
# copied verbatim by ora2pg and all three break the same way. Deliberately
# does NOT match SYS_CONNECT_BY_PATH: ora2pg genuinely converts that one
# into a working string concatenation inside the recursive CTE it builds
# (verified separately, see the research doc) -- flagging it would be a
# false positive on a construct that actually migrates fine.
_PSEUDOCOLUMN_RE = re.compile(
    r"\b(CONNECT_BY_ROOT|CONNECT_BY_ISLEAF|CONNECT_BY_ISCYCLE)\b",
    re.IGNORECASE,
)


def find_connect_by_pseudocolumns(source: str) -> list[Finding]:
    """Detect Oracle's CONNECT_BY_ROOT operator and the
    CONNECT_BY_ISLEAF/CONNECT_BY_ISCYCLE pseudocolumns. ora2pg rewrites
    the surrounding CONNECT BY into a WITH RECURSIVE but carries these
    three through unchanged, so the generated code fails to load.
    SYS_CONNECT_BY_PATH is deliberately excluded -- ora2pg does convert
    that one correctly. See
    docs/research/gap-039-connect-by-pseudocolumn.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PSEUDOCOLUMN_RE.finditer(visible):
        findings.append(
            Finding(
                detector="connect_by_pseudocolumn",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=m.group(1).upper(),
                message_id="connect_by_pseudocolumn",
            )
        )

    return findings
