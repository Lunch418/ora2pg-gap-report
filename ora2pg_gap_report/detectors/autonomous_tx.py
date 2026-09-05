import re

from ..models import Finding
from ..plsql_lex import (
    ROUTINE_START_RE,
    declare_and_begin,
    find_matching_end,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
    own_declare_text,
    qualified_name_pattern,
)

_PACKAGE_BODY_NAME_RE = re.compile(
    qualified_name_pattern(r"PACKAGE\s+BODY"),
    re.IGNORECASE,
)
_PRAGMA_RE = re.compile(r"PRAGMA\s+AUTONOMOUS_TRANSACTION\s*;", re.IGNORECASE)


def _package_name_at(package_matches: list[re.Match[str]], position: int) -> str:
    name = "UNKNOWN"
    for pm in package_matches:
        if pm.start() > position:
            break
        name = pm.group(1).upper()
    return name


def find_autonomous_transactions(source: str) -> list[Finding]:
    """Detect PRAGMA AUTONOMOUS_TRANSACTION inside PACKAGE BODY routines.

    PACKAGE BODY only, and that is the gap rather than the detector's
    limit. Re-measured against ora2pg 25.0:

      package body, with PRAGMA .... 6 units      standalone, with .... 4.2
      package body, without ........ 6 units      standalone, without .. 4.0

    Inside a package body ora2pg generates the whole autonomous-transaction
    workaround -- CREATE EXTENSION dblink, a connection string to fill in,
    a dblink() round trip per call -- and charges exactly nothing for it:
    the estimate is identical with and without the PRAGMA. That is GAP-001.
    For a standalone routine it does charge, and while 0.2 units (one
    minute) is arguably still light, "too little" is a judgement call and
    "nothing at all" is a fact. This project only registers gaps it has
    reproduced as broken, so the standalone case is deliberately not
    flagged; see docs/research/gap-001-autonomous-transaction.md.

    Handles multiple package bodies in one file, string/comment-aware
    scanning, and correctly excludes locally nested subprograms' own
    declare sections from their enclosing routine's — a nested routine's
    PRAGMA is neither dropped nor misattributed to the outer routine, it is
    simply out of scope (detecting *those* is a separate, smaller gap).

    A routine's PRAGMA can itself be hidden inside an EXECUTE IMMEDIATE
    argument that dynamically creates a package body at runtime (confirmed
    on real code: utPLSQL's own test suite does exactly this). All
    structural scanning here -- package/routine boundaries, BEGIN/END
    matching -- deliberately stays on `clean` (the fully safe-masked view)
    regardless: running it on a view where dynamic SQL is left visible
    would let a dynamically-created package/procedure name be picked up as
    if it were a real container declared in the source tree, misattributing
    unrelated findings to a name that doesn't exist anywhere in the static
    source.

    Only the final PRAGMA search uses the dynamic-SQL-visible view -- and
    over the routine's FULL span (declare section through its own END, not
    just the declare section a real PRAGMA is restricted to): a hidden
    PRAGMA lives inside an EXECUTE IMMEDIATE argument, which is itself an
    executable statement and can therefore only appear in a routine's own
    executable body (after its BEGIN), never in its declare section. Widening
    the search that far is still safe for a genuine (non-hidden) PRAGMA --
    Oracle's own grammar never allows a bare PRAGMA after BEGIN, so nothing
    real can newly match there -- and own_declare_text()'s nested_spans
    blanking (reused unchanged, just with the routine's own end_pos as the
    upper bound instead of begin_pos) still excludes every nested real
    subprogram's own span, since Oracle only allows nested subprogram
    declarations before BEGIN, all already captured in nested_spans.
    Positions are valid across both `clean` and `visible` since masking
    never changes length or newlines.
    """
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    package_matches = list(_PACKAGE_BODY_NAME_RE.finditer(clean))

    findings: list[Finding] = []
    cursor = 0
    hard_boundary = len(clean)

    for match in ROUTINE_START_RE.finditer(clean):
        if match.start() < cursor:
            continue  # nested inside a routine already resolved below

        resolved = declare_and_begin(clean, match.end(), hard_boundary)
        if resolved is None:
            continue
        declare_start, begin_pos, nested_spans = resolved

        end_pos = find_matching_end(clean, begin_pos, hard_boundary)
        if end_pos is None:
            continue
        cursor = end_pos

        # finditer(), not search(): a real routine has at most one PRAGMA
        # (Oracle rejects a second declaration in the same declare section),
        # but the widened visible-view range can legitimately contain a
        # second, hidden one inside dynamic SQL later in the same routine's
        # body -- search() would stop at the routine's own real PRAGMA (if
        # it has one) and never look further.
        routine_text = own_declare_text(visible, declare_start, end_pos, nested_spans)
        package_name = _package_name_at(package_matches, match.start())

        for pragma_match in _PRAGMA_RE.finditer(routine_text):
            absolute_pos = declare_start + pragma_match.start()
            line_no = line_at(clean, absolute_pos)

            findings.append(
                Finding(
                    detector="autonomous_tx",
                    severity="high",
                    object_name=f"{package_name}.{match.group(1).upper()}",
                    line=line_no,
                    snippet=pragma_match.group(0).strip(),
                    message_id="autonomous_tx",
                )
            )

    return findings
