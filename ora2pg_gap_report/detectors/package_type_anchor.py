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
_SLASH_RE = re.compile(r"^[ \t]*/[ \t\r]*$", re.MULTILINE)
_ROUTINE_BODY_RE = re.compile(r"^[ \t]*(?:FUNCTION|PROCEDURE)\b", re.IGNORECASE | re.MULTILINE)
_SUBTYPE_RE = re.compile(rf"\bSUBTYPE\s+({IDENTIFIER})\s+IS\b([^;]*?)%(ROW)?TYPE\b", re.IGNORECASE)
_RECORD_RE = re.compile(rf"\bTYPE\s+({IDENTIFIER})\s+IS\s+RECORD\s*\(", re.IGNORECASE)
_ANCHOR_RE = re.compile(r"%(?:ROW)?TYPE\b", re.IGNORECASE)


def package_sections(clean: str) -> list[tuple[re.Match[str], int, bool, str]]:
    """Each package spec or body in `clean`: its header match, where it
    ends (its `/`, the next package or the end), whether it is a body, and
    its name in upper case."""
    sections = []
    for package in _PACKAGE_START_RE.finditer(clean):
        ends = [len(clean)]
        nxt = _PACKAGE_START_RE.search(clean, package.end())
        if nxt:
            ends.append(nxt.start())
        slash = _SLASH_RE.search(clean, package.end())
        if slash:
            ends.append(slash.start())
        is_body = package.group(1) is not None
        sections.append((package, min(ends), is_body, (package.group(1) or package.group(2)).upper()))
    return sections


def package_level_end(clean: str, start: int, end: int, is_body: bool) -> int:
    """Where a package's own declarations stop: a spec declares nothing
    else, a body's routines start at its first FUNCTION/PROCEDURE."""
    if not is_body:
        return end
    routine = _ROUTINE_BODY_RE.search(clean, start, end)
    return routine.start() if routine else end


def find_package_type_anchor(source: str) -> list[Finding]:
    """Detect a package-level type anchored with %TYPE/%ROWTYPE: a RECORD
    field (`salary gx_emp.salary%TYPE`) or a SUBTYPE (`SUBTYPE t_name IS
    g_name_def%TYPE`).

    ora2pg 25.0 turns a package RECORD into CREATE TYPE pkg.r AS (...) and
    a SUBTYPE into CREATE DOMAIN pkg.t AS ..., and copies the anchor into
    both: `salary gx_emp.salary%TYPE`, `AS g_name_def%TYPE`. %TYPE exists
    only in PL/pgSQL declarations, not in SQL DDL, so PostgreSQL 16 rejects
    the statement ('syntax error at or near "%"'), and every routine that
    uses the type then fails too. Oracle 23ai compiles and runs the
    original. Found in the alexandria-plsql-utils samples
    (equitable_salaries_pkg, file_util_pkg). See
    docs/research/gap-120-package-type-anchor.md.

    Only package-level declarations: a type declared inside a routine stays
    a PL/pgSQL declaration, where %TYPE is valid."""
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    def add(pos: int, snippet: str) -> None:
        findings.append(
            Finding(
                detector="package_type_anchor",
                severity="high",
                object_name=enclosing_object_name(index, pos),
                line=line_at(clean, pos),
                snippet=snippet,
                message_id="package_type_anchor",
            )
        )

    for package, end, is_body, _ in package_sections(clean):
        stop = package_level_end(clean, package.end(), end, is_body)
        for m in _SUBTYPE_RE.finditer(clean, package.end(), stop):
            anchored = " ".join(m.group(2).split())
            add(m.start(2) + len(m.group(2)) - len(m.group(2).lstrip()),
                f"SUBTYPE {m.group(1)} IS {anchored}%{'ROW' if m.group(3) else ''}TYPE")
        for m in _RECORD_RE.finditer(clean, package.end(), stop):
            close = skip_balanced_parens(clean, m.end() - 1)
            anchor = _ANCHOR_RE.search(clean, m.end(), close)
            if anchor is not None:
                add(anchor.start(), f"TYPE {m.group(1)} IS RECORD (... {anchor.group(0)})")
    findings.sort(key=lambda f: f.line)
    return findings
