import re

from ..lex_common import call_arguments
from ..models import Finding
from ..plsql_lex import IDENTIFIER, enclosing_object_name, enclosing_object_name_index, line_at, mask_strings_and_comments

_HEADER_RE = re.compile(rf"\b(FUNCTION|PROCEDURE)\s+(?:{IDENTIFIER}\s*\.\s*)?{IDENTIFIER}\s*\(", re.IGNORECASE)
_DEFAULT_RE = re.compile(r"(?::=|\bDEFAULT\b)", re.IGNORECASE)
_MODE_RE = re.compile(rf"^\s*({IDENTIFIER})\s+(IN\s+OUT|OUT|IN)?\b", re.IGNORECASE)


def find_param_after_default(source: str) -> list[Finding]:
    """Detect a parameter without a default after one with a default:
    `p_text VARCHAR2 DEFAULT NULL, p_id OUT NUMBER` in a procedure,
    `a NUMBER := 1, b NUMBER` anywhere.

    Oracle allows it -- callers name the arguments. ora2pg 25.0 keeps the
    order, and PostgreSQL 16 rejects the routine: an input parameter after
    a default needs one too ('input parameters after one with a default
    value must also have defaults'), and so does a procedure's OUT
    parameter ('procedure OUT parameters cannot appear after one with a
    default value'); a function's OUT parameter may follow. Found in
    OraOpenSource Logger (ins_logger_logs). See
    docs/research/gap-146-param-after-default.md."""
    upper = source.upper()
    if "DEFAULT" not in upper and ":=" not in source:
        return []
    clean = mask_strings_and_comments(source)
    index = None
    findings: list[Finding] = []
    for m in _HEADER_RE.finditer(clean):
        is_procedure = m.group(1).upper() == "PROCEDURE"
        seen_default = False
        for param in call_arguments(clean, m.end() - 1):
            if _DEFAULT_RE.search(param):
                seen_default = True
                continue
            if not seen_default:
                continue
            mode = _MODE_RE.match(param)
            kind = " ".join((mode.group(2) or "IN").upper().split()) if mode else "IN"
            if kind == "OUT" and not is_procedure:
                continue
            if index is None:
                index = enclosing_object_name_index(clean)
            name = mode.group(1) if mode else param.strip()
            findings.append(
                Finding(
                    detector="param_after_default",
                    severity="high",
                    object_name=enclosing_object_name(index, m.start()),
                    # The routine's line: where PostgreSQL reports the error.
                    line=line_at(clean, m.start()),
                    snippet=f"{name} {kind} after a DEFAULT",
                    message_id="param_after_default",
                )
            )
            break  # one per routine: the first is what PostgreSQL reports
    return findings
