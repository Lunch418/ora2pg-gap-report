import re

from ..models import Finding
from ..plsql_lex import (
    IDENTIFIER,
    PACKAGE_BODY_NAME_RE,
    PACKAGE_SPEC_NAME_RE,
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

# A package-level constant or variable declaration with an initializer:
# 'name [CONSTANT] type [NOT NULL] := expr;' (or DEFAULT expr). Captures the
# name and the initializer expression.
_DECL_RE = re.compile(
    rf"^[ \t]*({IDENTIFIER})[ \t]+(?:CONSTANT\s+)?[^;:=\n]*?(?::=|\bDEFAULT\b)\s*([^;]*);",
    re.IGNORECASE | re.MULTILINE,
)
_ROUTINE_RE = re.compile(r"^\s*(?:FUNCTION|PROCEDURE|CURSOR)\b", re.IGNORECASE | re.MULTILINE)
_PACKAGE_START_RE = re.compile(
    PACKAGE_BODY_NAME_RE.pattern + "|" + PACKAGE_SPEC_NAME_RE.pattern, re.IGNORECASE
)


def find_package_constant_chain(source: str) -> list[Finding]:
    """Detect a package-level constant or variable whose initial value is
    computed from another package-level constant or variable
    (`c_stamp CONSTANT VARCHAR2(30) := c_date || ' HH24:MI';`).

    ora2pg rewrites every read of a package variable into a
    current_setting() call (GAP-036), and for this shape it splices the
    initializer's own rewritten reference after the first one, with the
    operator left dangling at the end: `RETURN
    current_setting('pkg.c_stamp')::varchar(30)current_setting('pkg.c_date')::varchar(30)||;`.
    That is not an expression at all, so every routine that reads the
    constant fails to load into PostgreSQL ('syntax error at or near "("').
    Reproduced with ora2pg 25.0 from a hand-written package and from
    DBMS_METADATA.GET_DDL; in Oracle 23ai the same package compiles and
    returns the combined value. See
    docs/research/gap-114-package-constant-chain.md.

    Only the package's own declare section is read: from the package
    header to its first FUNCTION/PROCEDURE/CURSOR. A local variable inside
    a routine is not package state and is not rewritten."""
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    findings: list[Finding] = []
    for package in _PACKAGE_START_RE.finditer(clean):
        start = package.end()
        routine = _ROUTINE_RE.search(clean, start)
        next_package = _PACKAGE_START_RE.search(clean, start)
        end = min(
            routine.start() if routine else len(clean),
            next_package.start() if next_package else len(clean),
        )
        section = clean[start:end]
        declared: list[str] = []
        for decl in _DECL_RE.finditer(section):
            name, initializer = decl.group(1), decl.group(2)
            if name.upper() in {"TYPE", "SUBTYPE", "PRAGMA"}:
                continue
            uses = [
                other
                for other in declared
                if re.search(rf"(?<![\w$#.]){re.escape(other)}(?![\w$#])", initializer, re.IGNORECASE)
            ]
            if uses:
                pos = start + decl.start(1)
                findings.append(
                    Finding(
                        detector="package_constant_chain",
                        severity="high",
                        object_name=f"{enclosing_object_name(index, pos)}.{name.upper()}",
                        line=line_at(clean, pos),
                        snippet=f"{name} := ... {uses[0]} ...",
                        message_id="package_constant_chain",
                    )
                )
            declared.append(name)
    return findings
