"""Automatic fixes for gaps where the correction is provably mechanical --
a pure text transformation with no semantic ambiguity, unlike the detector
library as a whole, which deliberately only ever flags and explains (see
docs/ARCHITECTURE.md: the detectors aren't a real parser, and rewriting
DDL that's about to be deployed carries a much higher cost of being wrong
than a missed or extra flag does).

Scope is deliberately narrow: GAP-028 (identity_column) is the only
candidate fixed here so far. It qualifies specifically because the bug is
a single, always-identical shape (ora2pg wraps its own correctly-derived
options clause in one extra, entirely redundant pair of parens) with a
single, always-correct fix (strip exactly that outer pair) -- there is no
case where the "buggy" shape is what the author actually meant, unlike
e.g. CROSS APPLY -> LATERAL (a real semantic rewrite with edge cases:
OUTER APPLY vs CROSS APPLY, subquery shape) or most other gaps in this
registry, which involve an actual design decision (rewrite to a temp
table? an array? a different clause entirely) that isn't this tool's to
make silently.

Operates on ora2pg's *generated* PostgreSQL output, not the Oracle
source -- the bug is in ora2pg's own substitution logic, not present in
or predictable from the Oracle DDL itself (see identity_column.py's own
detector, which flags the *Oracle* side as "this will trigger the bug
once migrated" -- a different file, a different point in the pipeline,
same reasoning --check-connect-by and --verify already use for "this
input is post-migration output, not pre-migration source")."""

import re

from .plsql_lex import skip_balanced_parens

_IDENTITY_WITH_OPTIONS_RE = re.compile(
    r"\bGENERATED\s+(?:ALWAYS|BY\s+DEFAULT(?:\s+ON\s+NULL)?)\s+AS\s+IDENTITY\s*\(",
    re.IGNORECASE,
)


def fix_identity_double_parens(source: str) -> tuple[str, int]:
    """Strip the extra outer pair of parens ora2pg wraps an IDENTITY
    column's sequence-options clause in ('IDENTITY ((...))' ->
    'IDENTITY (...)'). Returns (fixed_source, number_of_fixes_applied).

    Deliberately conservative about what counts as "this exact bug", not
    just "any double parens after IDENTITY": requires the first character
    after IDENTITY's own '(' to be a second, immediately-adjacent '(' (no
    correctly-converted IDENTITY clause is ever '((' -- a correct one is
    always plain '(', see docs/research/gap-028-identity-column.md), and
    requires that second, inner '('s own matching ')' is *immediately*
    followed by the outer '('s matching ')' -- i.e. nothing else lives
    inside the outer pair besides the inner group. A double-parenthesized
    options clause with something else alongside it inside the outer
    pair would not match this shape (never actually observed, but this
    function has no business guessing what to do with it) and is left
    untouched rather than risking a wrong rewrite."""
    out = []
    pos = 0
    count = 0
    for m in _IDENTITY_WITH_OPTIONS_RE.finditer(source):
        outer_open = m.end() - 1
        if outer_open < pos:
            continue  # inside a span already consumed by an earlier fix
        if source[outer_open + 1 : outer_open + 2] != "(":
            continue  # single '(' -- already correct, nothing to fix
        inner_open = outer_open + 1
        inner_close = skip_balanced_parens(source, inner_open)
        outer_close = skip_balanced_parens(source, outer_open)
        if inner_close != outer_close - 1:
            continue  # not a pure double-wrap -- leave it alone
        out.append(source[pos:outer_open])
        out.append(source[inner_open:inner_close])
        pos = outer_close
        count += 1
    out.append(source[pos:])
    return "".join(out), count
