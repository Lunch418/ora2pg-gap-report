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
    skip_balanced_parens,
)

_PACKAGE_START_RE = re.compile(PACKAGE_BODY_NAME_RE.pattern + "|" + PACKAGE_SPEC_NAME_RE.pattern, re.IGNORECASE)
_ROUTINE_HEAD_RE = re.compile(rf"\b(?:FUNCTION|PROCEDURE)\s+{IDENTIFIER}\s*\(", re.IGNORECASE)
# A parameter's default: ':= x' or 'DEFAULT x', where x is a bare name,
# optionally qualified (pkg.c_name), and nothing else follows before the
# next parameter or the end of the list.
_DEFAULT_RE = re.compile(
    rf"(?::=|\bDEFAULT\b)\s*((?:{IDENTIFIER}\s*\.\s*)?{IDENTIFIER})\s*(?=,|$)",
    re.IGNORECASE,
)
# Defaults that are not package state: literals spelled as keywords and the
# built-in functions ora2pg converts.
_BUILT_IN = frozenset(
    {
        "NULL", "TRUE", "FALSE", "SYSDATE", "SYSTIMESTAMP", "USER", "UID",
        "CURRENT_DATE", "CURRENT_TIMESTAMP", "LOCALTIMESTAMP", "SESSIONTIMEZONE", "DBTIMEZONE",
    }
)


def find_package_constant_default(source: str) -> list[Finding]:
    """Detect a routine parameter in a package whose default is a package
    constant or variable (`p_os IN VARCHAR2 := g_os_windows`).

    ora2pg rewrites every read of a package variable inside a routine body
    into current_setting() (GAP-036), but not one in a parameter default:
    `p_os text DEFAULT g_os_windows` is copied as it is, and PostgreSQL,
    which has no such name in scope, rejects the function at load time
    ('column "g_os_windows" does not exist'). Reproduced with ora2pg 25.0
    from DBMS_METADATA.GET_DDL; in Oracle 23ai the package compiles and the
    default applies. Found in alexandria-plsql-utils' file_util_pkg. See
    docs/research/gap-119-package-constant-default.md.

    The default must be a bare name: a literal, an expression or a function
    call is not this gap, and neither is a keyword-like built-in (NULL,
    TRUE, SYSDATE, ...). A package body is often exported without its spec,
    so the name is not required to be declared in the same file."""
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    findings: list[Finding] = []
    for package in _PACKAGE_START_RE.finditer(clean):
        next_package = _PACKAGE_START_RE.search(clean, package.end())
        end = next_package.start() if next_package else len(clean)
        for head in _ROUTINE_HEAD_RE.finditer(clean, package.end(), end):
            open_paren = head.end() - 1
            close = skip_balanced_parens(clean, open_paren)
            for param in _split_params(clean[open_paren + 1 : close - 1]):
                text, offset = param
                m = _DEFAULT_RE.search(text)
                if m is None:
                    continue
                name = m.group(1)
                if re.sub(r"\s+", "", name).upper() in _BUILT_IN:
                    continue
                pos = open_paren + 1 + offset + m.start(1)
                compact = re.sub(r"\s+", "", name)
                findings.append(
                    Finding(
                        detector="package_constant_default",
                        severity="high",
                        object_name=enclosing_object_name(index, pos),
                        line=line_at(clean, pos),
                        snippet=f"DEFAULT {compact}",
                        message_id="package_constant_default",
                    )
                )
    return findings


def _split_params(text: str) -> list[tuple[str, int]]:
    """The parameters of a list, split on top-level commas, each with its
    offset in `text`."""
    params: list[tuple[str, int]] = []
    depth = 0
    start = 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            params.append((text[start:i], start))
            start = i + 1
    params.append((text[start:], start))
    return [(p.rstrip(), off) for p, off in params]
