import re

from ..models import Finding
from ..plsql_lex import (
    IDENTIFIER,
    PACKAGE_BODY_NAME_RE,
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_PROCEDURE_RE = re.compile(rf"^\s*PROCEDURE\s+({IDENTIFIER})", re.IGNORECASE | re.MULTILINE)
# A call statement: at the start of a statement (after ';', BEGIN, THEN,
# ELSE or LOOP), an optionally package-qualified name, then '(' or ';'.
_CALL_RE = re.compile(
    rf"(?:;|\bBEGIN\b|\bTHEN\b|\bELSE\b|\bLOOP\b)\s*(?:({IDENTIFIER})\s*\.\s*)?({IDENTIFIER})\s*(?=([(;]))",
    re.IGNORECASE,
)


def find_repeated_package_call(source: str) -> list[Finding]:
    """Detect `pkg.proc;` -- a call to a procedure of the same package,
    qualified with the package name and written without parentheses --
    when the same routine has already called that procedure.

    ora2pg converts a call inside a package body to `CALL pkg.proc();`,
    but for this shape only the first one: the repeat comes out as
    `pkg.proc();` with no CALL, which PL/pgSQL rejects ('syntax error at or
    near "pkg"'), so the routine does not load. An unqualified repeat, or
    one written with parentheses or arguments, converts correctly; so does
    the same call in a different routine. Reproduced with ora2pg 25.0;
    Oracle 23ai runs the original. See
    docs/research/gap-116-repeated-package-call.md."""
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    findings: list[Finding] = []
    for package in PACKAGE_BODY_NAME_RE.finditer(clean):
        pkg = package.group(1).upper()
        next_package = PACKAGE_BODY_NAME_RE.search(clean, package.end())
        end = next_package.start() if next_package else len(clean)
        body = clean[package.end() : end]
        procedures = {m.group(1).upper() for m in _PROCEDURE_RE.finditer(body)}
        seen: dict[str, set[str]] = {}  # routine -> procedures it has called
        for call in _CALL_RE.finditer(body):
            qualifier, name, after = call.group(1), call.group(2).upper(), call.group(3)
            if name not in procedures or (qualifier is not None and qualifier.upper() != pkg):
                continue
            pos = package.end() + call.start(2)
            routine = enclosing_object_name(index, pos)
            called = seen.setdefault(routine, set())
            if qualifier is not None and after == ";" and name in called:
                findings.append(
                    Finding(
                        detector="repeated_package_call",
                        severity="high",
                        object_name=routine,
                        line=line_at(clean, pos),
                        snippet=f"{qualifier}.{call.group(2)};",
                        message_id="repeated_package_call",
                    )
                )
            called.add(name)
    return findings
