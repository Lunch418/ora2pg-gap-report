import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

# Distinct from connect_by.py: that module lints ora2pg's *generated*
# output for the LEVEL substitution bug in the plain/basic CONNECT BY
# case (which otherwise converts, just imperfectly). NOCYCLE and ORDER
# SIBLINGS BY are a different, much more severe failure mode -- confirmed
# to make ora2pg's parser corrupt the surrounding PL/SQL block structure
# itself, not just mistranslate a keyword -- so this detector works at
# the Oracle source level instead, like most others in this project, and
# doesn't need a real ora2pg invocation to flag it.
_NOCYCLE_RE = re.compile(r"\bCONNECT\s+BY\s+NOCYCLE\b", re.IGNORECASE)
_ORDER_SIBLINGS_RE = re.compile(r"\bORDER\s+SIBLINGS\s+BY\b", re.IGNORECASE)


def find_connect_by_nocycle_or_order_siblings(source: str) -> list[Finding]:
    """Detect Oracle's CONNECT BY NOCYCLE and ORDER SIBLINGS BY. Confirmed
    to cause severe structural corruption in ora2pg's PL/SQL block
    conversion, not just an imprecise translation -- see
    docs/research/gap-014-connect-by-nocycle.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for pattern, snippet in ((_NOCYCLE_RE, "CONNECT BY NOCYCLE"), (_ORDER_SIBLINGS_RE, "ORDER SIBLINGS BY")):
        for m in pattern.finditer(visible):
            findings.append(
                Finding(
                    detector="connect_by_nocycle",
                    severity="high",
                    object_name=enclosing_object_name(name_index, m.start()),
                    line=line_at(clean, m.start()),
                    snippet=snippet,
                    message_id="connect_by_nocycle",
                )
            )

    return findings
