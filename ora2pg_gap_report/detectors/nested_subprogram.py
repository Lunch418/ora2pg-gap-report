import re

from ..models import Finding
from ..plsql_lex import (
    PACKAGE_BODY_NAME_RE,
    ROUTINE_START_RE,
    STANDALONE_ROUTINE_RE,
    declare_and_begin,
    find_matching_end,
    is_inside_grant_or_revoke_statement,
    line_at,
    mask_strings_and_comments,
)


def _package_name_at(package_matches: list, position: int) -> str | None:
    name = None
    for pm in package_matches:
        if pm.start() > position:
            break
        name = pm.group(1).upper()
    return name


def find_nested_subprograms(source: str) -> list[Finding]:
    """Detect a Oracle PROCEDURE/FUNCTION declared locally inside another
    block's own declare section -- ora2pg doesn't preserve the nesting at
    all: the nested routine leaks out as a separate top-level object, its
    containing block vanishes from the output entirely, and the nested
    routine's own body gets corrupted (the containing block's executable
    section is glued onto it after its own END). See
    docs/research/gap-034-nested-subprogram.md.

    Both standalone routines (STANDALONE_ROUTINE_RE, 'CREATE [OR REPLACE]
    FUNCTION/PROCEDURE name') and package-body member routines
    (ROUTINE_START_RE, 'FUNCTION/PROCEDURE name' at the start of a line,
    no CREATE prefix -- the only form Oracle allows for a *nested*
    declaration too) are treated as potential outer entry points, tagged
    by which regex found them, merged and processed in position order
    with a shared cursor -- same single-pass-no-reprocessing pattern as
    autonomous_tx.py, extended to cover both match kinds so a routine
    matched by STANDALONE_ROUTINE_RE whose own 'CREATE ... PROCEDURE'
    header happens to wrap onto a second line (where ROUTINE_START_RE's
    own line-start anchor would otherwise also match that second line)
    isn't double-processed. The tag also drives attribution directly (a
    package member's own name is qualified by its nearest preceding
    PACKAGE_BODY_NAME_RE match, a standalone routine's isn't) --
    deliberately not via enclosing_object_name_index()/
    enclosing_object_name(): that shared helper additionally scans for
    trigger/view containers this detector has no use for, redundantly
    re-running the same ROUTINE_START_RE/STANDALONE_ROUTINE_RE finditer()
    calls already done here.

    declare_and_begin()'s own nested_spans recursion already walks
    arbitrarily deep nesting in one call, so every entry it returns for
    a given top-level entry point is reported here, all attributed to
    that same top-level entry point -- not to whichever intermediate
    routine directly contains it, a deliberate simplification for a
    heuristic tool rather than a real parser."""
    clean = mask_strings_and_comments(source)
    package_matches = list(PACKAGE_BODY_NAME_RE.finditer(clean))
    findings: list[Finding] = []

    outer_matches = sorted(
        # ROUTINE_START_RE has no CREATE prefix, so it isn't subject to the
        # GRANT/REVOKE check below (same reasoning as
        # enclosing_object_name_index()'s own comment on this) -- only
        # STANDALONE_ROUTINE_RE's CREATE-anchored match can be a
        # GRANT/REVOKE statement's privilege list ('GRANT CREATE
        # PROCEDURE TO ...') masquerading as a real declaration.
        [(m, "package_member") for m in ROUTINE_START_RE.finditer(clean)]
        + [
            (m, "standalone")
            for m in STANDALONE_ROUTINE_RE.finditer(clean)
            if not is_inside_grant_or_revoke_statement(clean, m.start())
        ],
        key=lambda pair: pair[0].start(),
    )
    cursor = 0
    hard_boundary = len(clean)

    for match, kind in outer_matches:
        if match.start() < cursor:
            continue  # nested inside an outer entry point already resolved below

        resolved = declare_and_begin(clean, match.end(), hard_boundary)
        if resolved is None:
            continue
        _declare_start, begin_pos, nested_spans = resolved

        end_pos = find_matching_end(clean, begin_pos, hard_boundary)
        if end_pos is None:
            continue
        cursor = end_pos

        if not nested_spans:
            continue

        outer_name = match.group(1).upper()
        if kind == "package_member":
            package_name = _package_name_at(package_matches, match.start())
            outer_object_name = f"{package_name}.{outer_name}" if package_name else outer_name
        else:
            outer_object_name = outer_name

        for nested_start, _nested_end in nested_spans:
            nested_match = ROUTINE_START_RE.match(clean, nested_start)
            nested_name = nested_match.group(1).upper() if nested_match else "UNKNOWN"
            snippet = (
                re.sub(r"\s+", " ", nested_match.group(0).strip()) if nested_match else "UNKNOWN"
            )

            findings.append(
                Finding(
                    detector="nested_subprogram",
                    severity="high",
                    object_name=f"{outer_object_name}.{nested_name}",
                    line=line_at(clean, nested_start),
                    snippet=snippet,
                    message_id="nested_subprogram",
                )
            )

    return findings
