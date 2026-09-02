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


# `position(''needle'' in haystack)` -- ora2pg's own CHARINDEX translation
# picks the right target function but doubles the quotes around the search
# string (GAP-100). The needle is required to be non-empty and to contain
# no quote of its own, which is what makes the rewrite unambiguous: with
# those two conditions the text can only ever be the broken shape.
# `position('' in x)` (a genuine, if pointless, search for the empty
# string) has an empty needle and is left alone; `position('a''b' in x)`
# is a valid single literal containing an escaped quote and never matches
# in the first place, since the needle would have to contain a quote.
# The ` in` tail is captured rather than rewritten so the surrounding
# whitespace comes through byte-for-byte -- the fix touches the two
# doubled quotes and nothing else, which keeps its diff to exactly what
# it claims to change.
_MSSQL_DOUBLED_QUOTE_POSITION_RE = re.compile(
    r"(\bposition\s*\(\s*)''([^']+)''(\s+in\b)",
    re.IGNORECASE,
)


def fix_mssql_charindex_quotes(source: str) -> tuple[str, int]:
    """Undo the doubled quotes in ora2pg's `position(''x'' in y)` output
    ('' -> '), returning (fixed_source, number_of_fixes_applied).

    Qualifies as mechanical for the same reason GAP-028's fix does: the
    shape is never valid SQL to begin with -- PostgreSQL parses ''x'' as
    an empty literal followed by a bare identifier and fails with
    'syntax error at or near "x"' (confirmed on a real PostgreSQL 16 run,
    docs/research/gap-100-mssql-charindex.md) -- so there is no reading
    under which the current text is what anyone meant, and exactly one
    correct rewrite. Note this fixes the *quoting* only: CHARINDEX's
    optional third argument (start position) has no position()
    equivalent and is a semantic rewrite, so a three-argument call is
    left for a human, as its research doc says."""
    count = 0

    def _replace(m: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"{m.group(1)}'{m.group(2)}'{m.group(3)}"

    return _MSSQL_DOUBLED_QUOTE_POSITION_RE.sub(_replace, source), count


# The empty declaration block ora2pg emits for a parameterless T-SQL
# procedure (GAP-091): the literal lines `DECLARE`, blank, `;` with
# nothing else before `BEGIN`. Anchored to a line start and required to
# run all the way to BEGIN, so a DECLARE block that actually declares
# something -- which always has a name before its `;` -- cannot match.
_MSSQL_EMPTY_DECLARE_RE = re.compile(
    r"^[ \t]*DECLARE[ \t]*\r?\n"  # the DECLARE line itself
    r"(?:[ \t]*\r?\n)*"  # blank lines, however many
    r"[ \t]*;[ \t]*\r?\n"  # the stray lone semicolon
    r"(?:[ \t]*\r?\n)*"  # blank lines again
    r"(?=[ \t]*BEGIN\b)",  # ... immediately followed by BEGIN
    re.IGNORECASE | re.MULTILINE,
)


def fix_mssql_empty_declare(source: str) -> tuple[str, int]:
    """Delete the unparseable empty `DECLARE ;` block ora2pg generates for
    a parameterless T-SQL procedure, returning (fixed_source,
    number_of_fixes_applied).

    Mechanical for the same reason as the other two fixes here: PL/pgSQL
    rejects the block outright ('syntax error at or near ";"', confirmed
    on a real PostgreSQL 16 run, docs/research/
    gap-091-mssql-parameterless-procedure.md), an empty DECLARE declares
    nothing by definition, and the correct output is precisely the same
    routine without it -- which is exactly what ora2pg itself emits for
    the same procedure when it happens to take a parameter (verified by
    A/B in that same research doc). The match requires a lone `;` as the
    block's only content: a DECLARE with real declarations always has a
    variable name in front of its semicolon and cannot match."""
    fixed, count = _MSSQL_EMPTY_DECLARE_RE.subn("", source)
    return fixed, count


# Which mechanical fixes apply to which source dialect's generated output.
# Keyed by the same dialect names core.DIALECTS carries. MySQL has no
# entry with fixes on purpose, not by oversight: of its 19 confirmed
# gaps, every one is either a construct ora2pg copies verbatim and whose
# correct replacement is a real design decision (ON DUPLICATE KEY UPDATE
# -> ON CONFLICT changes trigger/cascade behaviour; INSERT IGNORE ->
# ON CONFLICT DO NOTHING is narrower than IGNORE), or a loss that cannot
# be reconstructed from the generated output at all -- GAP-068's missing
# CREATE TYPE needs the enum values, which only exist in the MySQL source
# this file no longer is. Inventing a fix for those would be exactly the
# "rewriting DDL that's about to be deployed" this module's docstring
# rules out.
FIXERS_BY_DIALECT: dict[str, tuple] = {
    "oracle": (fix_identity_double_parens,),
    "mysql": (),
    "mssql": (fix_mssql_charindex_quotes, fix_mssql_empty_declare),
}
