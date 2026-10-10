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


def _first_uses(clean: str, names: "set[str]", start: int, end: int) -> "dict[str, re.Match[str]]":
    """For each of `names`, its first use in clean[start:end] that
    _usage_re(name) matches and that is not inside another type's
    declaration -- in one pass over the section for all the names, from
    their occurrences, each checked by the full pattern in a short window
    before it. Running the pattern, which opens with "any identifier",
    over a large package once per name was most of this detector's time."""
    alternatives = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    occurrence = re.compile(rf"(?<![A-Za-z0-9_$#])({alternatives})\b", re.IGNORECASE)
    first: dict[str, re.Match[str]] = {}
    last_end: dict[str, int] = {}
    for occ in occurrence.finditer(clean, start, end):
        name = occ.group(1).upper()
        if name in first or occ.start() < last_end.get(name, start):
            continue
        floor = last_end.get(name, start)
        window = max(floor, occ.start() - 200)
        # A prefix whose whitespace (masked comments) runs past the window
        # still has to be seen whole.
        while window > floor and clean[window - 1].isspace():
            window -= 1
        while window > floor and not clean[window - 1].isspace() and not clean[window].isspace():
            window -= 1
        for m in _usage_re(name).finditer(clean, window, end):
            if m.start(1) > occ.start():
                break
            if m.start(1) == occ.start():
                last_end[name] = m.end()
                statement_start = max(clean.rfind(";", 0, m.start()), 0)
                if not _STATEMENT_START_RE.match(clean, statement_start):
                    first[name] = m
                break
        if len(first) == len(names):
            break
    return first


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
        names = declared.get(owner)
        if not names:
            continue
        # Uses inside another type's declaration are skipped: ora2pg
        # qualifies those.
        uses = sorted((m.start(1), m.group(1)) for m in _first_uses(clean, names, first_routine.start(), end).values())
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
