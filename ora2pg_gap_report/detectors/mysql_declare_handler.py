import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_HANDLER_RE = re.compile(
    r"\bDECLARE\s+(CONTINUE|EXIT|UNDO)\s+HANDLER\b",
    re.IGNORECASE,
)


def find_mysql_declare_handlers(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's DECLARE ... HANDLER condition handlers.
    ora2pg -m drops them entirely, emitting no PL/pgSQL EXCEPTION block
    in their place, so a routine's whole error-handling policy silently
    disappears -- errors MySQL swallowed now propagate to the caller.
    See docs/research/gap-084-mysql-declare-handler.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _HANDLER_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_declare_handler",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=f"DECLARE {m.group(1).upper()} HANDLER",
                message_id="mysql_declare_handler",
            )
        )

    return findings
