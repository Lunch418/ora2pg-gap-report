import re

from ..models import Finding
from ..plsql_lex import (
    IDENTIFIER,
    line_at,
    mask_strings_and_comments,
    qualified_name_pattern,
    skip_balanced_parens,
)

_CREATE_TRIGGER_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:EDITIONABLE\s+|NONEDITIONABLE\s+)?TRIGGER"),
    re.IGNORECASE,
)
_BODY_START_RE = re.compile(r"\b(?:DECLARE|BEGIN)\b", re.IGNORECASE)
_END_OF_TRIGGER_RE = re.compile(r"^[ \t]*/[ \t\r]*$|\bCREATE\s+(?:OR\s+REPLACE\s+)?", re.IGNORECASE | re.MULTILINE)
# A package procedure called as a statement: 'pkg.proc;' or 'pkg.proc(...);'
# at the start of a statement.
_CALL_RE = re.compile(
    rf"(?:;|\bBEGIN\b|\bTHEN\b|\bELSE\b|\bLOOP\b)\s*({IDENTIFIER})\s*\.\s*({IDENTIFIER})\s*(?=[(;])",
    re.IGNORECASE,
)
# Not package procedures: the row pseudo-records, and the built-in
# packages dbms_utl_calls already reports.
_NOT_A_PACKAGE_RE = re.compile(r"^(?:NEW|OLD|PARENT|DBMS_\w*|UTL_\w*)$", re.IGNORECASE)


def find_trigger_package_call(source: str) -> list[Finding]:
    """Detect a trigger body calling a package procedure as a statement
    (`audit_pkg.log_change(:NEW.id);`, `audit_pkg.touch;`).

    Inside a package ora2pg turns such a call into `CALL pkg.proc(...)`,
    because it has the package in the same run and knows the name is a
    procedure. A trigger is converted on its own (-t TRIGGER), so the
    call is copied as written, and PL/pgSQL rejects a bare procedure call
    ('syntax error at or near "audit_pkg"'): the trigger function does not
    load, and neither does the trigger. A function used in an expression
    (`v := pkg.f(x);`) is fine. Reproduced with ora2pg 25.0; Oracle 23ai
    runs the original. See docs/research/gap-117-trigger-package-call.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []
    for trigger in _CREATE_TRIGGER_RE.finditer(clean):
        body = _BODY_START_RE.search(clean, trigger.end())
        if body is None:
            continue
        stop = _END_OF_TRIGGER_RE.search(clean, body.end())
        end = stop.start() if stop else len(clean)
        for call in _CALL_RE.finditer(clean, body.start(), end):
            if _NOT_A_PACKAGE_RE.match(call.group(1)):
                continue
            after = call.end()
            if clean[after] == "(":
                after = skip_balanced_parens(clean, after)
            if not clean[after:].lstrip().startswith(";"):
                continue  # an expression, not a call statement
            findings.append(
                Finding(
                    detector="trigger_package_call",
                    severity="high",
                    object_name=trigger.group(1).upper(),
                    line=line_at(clean, call.start(1)),
                    snippet=f"{call.group(1)}.{call.group(2)}",
                    message_id="trigger_package_call",
                )
            )
    return findings
