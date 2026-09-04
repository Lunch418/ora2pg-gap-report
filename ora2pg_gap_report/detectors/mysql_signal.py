import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_SIGNAL_RE = re.compile(r"\b(SIGNAL|RESIGNAL)\b", re.IGNORECASE)


def find_mysql_signal_statements(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's SIGNAL and RESIGNAL statements. ora2pg -m
    copies them through unchanged and PL/pgSQL has no such statement at
    all, so the containing procedure/function loads cleanly (bodies are
    not checked) and then fails on its first call. See docs/research/
    gap-071-mysql-signal.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _SIGNAL_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_signal",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=m.group(1).upper(),
                message_id="mysql_signal",
            )
        )

    return findings
