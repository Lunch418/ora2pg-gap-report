import re

from ..models import Finding
from ..plsql_lex import (
    IDENTIFIER,
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)
from .package_type_anchor import package_level_end, package_sections

# A package-level type: TYPE x IS RECORD/TABLE/VARRAY ..., SUBTYPE x IS ...
# A REF CURSOR type is GAP-115's: its CREATE TYPE fails on its own.
_TYPE_DECL_RE = re.compile(rf"\b(?:SUB)?TYPE\s+({IDENTIFIER})\s+IS\s+(?!REF\b)", re.IGNORECASE)
_ROUTINE_RE = re.compile(rf"^[ \t]*(?:FUNCTION|PROCEDURE)\s+{IDENTIFIER}", re.IGNORECASE | re.MULTILINE)
_STATEMENT_START_RE = re.compile(r"(?:^|;)\s*(?:SUB)?TYPE\b", re.IGNORECASE)


def _usage_re(name: str) -> re.Pattern[str]:
    # A variable or parameter of the type -- `v t_code;`, `p IN t_code`,
    # `p IN OUT NOCOPY t_code` -- or a function's RETURN type. Not
    # `pkg.t_code` (ora2pg keeps the qualifier, and it loads), not
    # `t_code.x` or `t_code(...)`.
    n = re.escape(name)
    return re.compile(
        rf"(?:(?<![.\w$#]){IDENTIFIER}\s+(?:IN\s+OUT\s+|IN\s+|OUT\s+)?(?:NOCOPY\s+)?"
        rf"|\bRETURN\s+)(?<![.\w$#]\.)({n})\b(?!\s*[.(%])",
        re.IGNORECASE,
    )


def find_package_type_reference(source: str) -> list[Finding]:
    """Detect a package-level type (TYPE ... IS RECORD/TABLE OF/VARRAY,
    SUBTYPE) used without the package name in the package's own routines:
    a parameter, a variable, a RETURN type.

    ora2pg 25.0 creates the type in the package's schema -- CREATE TYPE
    pkg.pair_rt, CREATE DOMAIN pkg.t_code -- but copies the routines'
    references as they are: `r pair_rt;`, `p t_code`, `RETURNS T_CODE`.
    The package's schema is not on the search_path, so PostgreSQL 16
    rejects every such routine at load time ('type "pair_rt" does not
    exist'), even when the type itself loaded. Oracle 23ai resolves the
    name inside its own package. A qualified reference (pkg.t_code) is
    kept qualified and loads. See
    docs/research/gap-121-package-type-reference.md.

    Reported once per type, at its first unqualified use. A body exported
    without its spec declares nothing, so only types declared in the same
    file are known."""
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    sections = package_sections(clean)
    declared: dict[str, set[str]] = {}  # package -> type names
    for package, end, is_body, owner in sections:
        stop = package_level_end(clean, package.end(), end, is_body)
        for m in _TYPE_DECL_RE.finditer(clean, package.end(), stop):
            declared.setdefault(owner, set()).add(m.group(1).upper())

    findings: list[Finding] = []
    reported: set[tuple[str, str]] = set()
    for package, end, _, owner in sections:
        first_routine = _ROUTINE_RE.search(clean, package.end(), end)
        if first_routine is None:
            continue
        uses: list[tuple[int, str]] = []
        for name in declared.get(owner, ()):
            for m in _usage_re(name).finditer(clean, first_routine.start(), end):
                statement_start = max(clean.rfind(";", 0, m.start()), 0)
                if _STATEMENT_START_RE.match(clean, statement_start):
                    continue  # inside another type's declaration: ora2pg qualifies those
                uses.append((m.start(1), m.group(1)))
                break
        for pos, written in sorted(uses):
            if (owner, written.upper()) in reported:
                continue
            reported.add((owner, written.upper()))
            findings.append(
                Finding(
                    detector="package_type_reference",
                    severity="high",
                    object_name=enclosing_object_name(index, pos),
                    line=line_at(clean, pos),
                    snippet=written,
                    message_id="package_type_reference",
                )
            )
    findings.sort(key=lambda f: f.line)
    return findings
