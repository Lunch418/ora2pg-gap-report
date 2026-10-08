"""Automatic fixes for gaps where the correction is provably mechanical --
a pure text transformation with no semantic ambiguity, unlike the detector
library as a whole, which deliberately only ever flags and explains (see
docs/ARCHITECTURE.md: the detectors aren't a real parser, and rewriting
DDL that's about to be deployed carries a much higher cost of being wrong
than a missed or extra flag does).

Scope is deliberately narrow: six gaps so far (GAP-028, GAP-024 and
GAP-123 for Oracle, GAP-075 for MySQL, GAP-100 and GAP-091 for T-SQL, see
FIXERS_BY_DIALECT). GAP-028,
the first, shows what qualifies: it qualifies specifically because the bug is
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
from collections.abc import Callable

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


# What may follow a WITH list in Oracle and needs a different spelling in
# PostgreSQL (SEARCH ... SET, CYCLE ... SET ... TO ... DEFAULT): a WITH
# carrying one is left for a human, since adding RECURSIVE alone would not
# make it load.
_SEARCH_OR_CYCLE_RE = re.compile(r"\s*(?:SEARCH|CYCLE)\b", re.IGNORECASE)


def fix_recursive_with_keyword(source: str) -> tuple[str, int]:
    """Add the RECURSIVE keyword PostgreSQL requires to a WITH whose CTE
    refers to itself (GAP-024), returning (fixed_source, number_of_fixes).

    Mechanical because of what the self-reference means on each side.
    Oracle has no keyword: a CTE that names itself in its own body *is*
    recursive, by definition. PostgreSQL, without RECURSIVE, resolves that
    name to a table instead and fails ('relation "tree" does not exist',
    confirmed by loading ora2pg 25.0's output into PostgreSQL 16), or, if a
    table of that name happens to exist, silently reads the table. Adding
    the keyword gives exactly Oracle's meaning, and RECURSIVE on a WITH
    list changes nothing for its non-recursive members.

    Which WITH is recursive is decided by the recursive_with detector's own
    rules (a UNION, then the CTE's name in a FROM/JOIN/list position), so
    the fix touches exactly what the detector reports. A WITH followed by
    Oracle's SEARCH or CYCLE clause is skipped: those are spelled
    differently in PostgreSQL and need a person."""
    from .detectors.recursive_with import _NEXT_CTE_RE, _UNION_RE, _WITH_CTE_RE
    from .plsql_lex import mask_dynamic_sql_visible

    visible = mask_dynamic_sql_visible(source)
    insert_at: list[int] = []
    for m in _WITH_CTE_RE.finditer(visible):
        ctes = [(m.group(1), m.end() - 1)]
        pos = skip_balanced_parens(visible, m.end() - 1)
        while True:
            next_m = _NEXT_CTE_RE.match(visible, pos)
            if next_m is None:
                break
            ctes.append((next_m.group(1), next_m.end() - 1))
            pos = skip_balanced_parens(visible, next_m.end() - 1)
        if _SEARCH_OR_CYCLE_RE.match(visible, pos):
            continue
        for name, body_start in ctes:
            body = visible[body_start : skip_balanced_parens(visible, body_start)]
            union = _UNION_RE.search(body)
            if union is None:
                continue
            self_ref = re.compile(rf"(?:\bFROM\s+|\bJOIN\s+|,\s*){re.escape(name)}\b", re.IGNORECASE)
            if self_ref.search(body, union.end()):
                insert_at.append(m.start() + len("WITH"))
                break

    fixed = source
    for at in reversed(insert_at):
        fixed = fixed[:at] + " RECURSIVE" + fixed[at:]
    return fixed, len(insert_at)


# MySQL's `LIMIT offset, count`. MySQL accepts only a literal or a routine
# variable in either place, never an expression, so the operands are a
# number or a plain name, and what follows the count must not continue an
# expression -- anything else is left alone rather than guessed at.
_MYSQL_LIMIT_COMMA_RE = re.compile(
    r"\b(?P<kw>LIMIT)(?P<sp>\s+)(?P<offset>\d+|[A-Za-z_]\w*)\s*,\s*(?P<count>\d+|[A-Za-z_]\w*)\b(?!\s*[-+*/%(.\[])",
    re.IGNORECASE,
)


def fix_mysql_limit_comma(source: str) -> tuple[str, int]:
    """Rewrite MySQL's `LIMIT offset, count`, which ora2pg copies as it is,
    to PostgreSQL's `LIMIT count OFFSET offset` (GAP-075), returning
    (fixed_source, number_of_fixes_applied).

    Mechanical for the same reason as the others: PostgreSQL rejects the
    comma form outright -- 'LIMIT #,# syntax is not supported', confirmed by
    loading ora2pg 25.0's -m output into PostgreSQL 16 -- so the text never
    means anything as it stands, and the rewrite only moves the two
    operands into the order PostgreSQL spells. Searched for in code only:
    string literals, quoted identifiers and comments are masked first
    (pg_script.mask_literals)."""
    from .pg_script import mask_literals

    masked = mask_literals(source)
    out: list[str] = []
    pos = 0
    count = 0
    for m in _MYSQL_LIMIT_COMMA_RE.finditer(masked):
        out.append(source[pos : m.start()])
        out.append(f"{source[m.start('kw'):m.end('kw')]}{m.group('sp')}{m.group('count')} OFFSET {m.group('offset')}")
        pos = m.end()
        count += 1
    out.append(source[pos:])
    return "".join(out), count



# pg_sleep(...) at the start of a PL/pgSQL statement -- after a `;`,
# BEGIN, THEN, ELSE or LOOP -- not after PERFORM or SELECT or inside an
# expression.
_BARE_PG_SLEEP_RE = re.compile(r"(?:;|\bBEGIN\b|\bTHEN\b|\bELSE\b|\bLOOP\b)\s*(?=pg_sleep\s*\()", re.IGNORECASE)


def fix_bare_pg_sleep(source: str) -> tuple[str, int]:
    """Write the PERFORM that ora2pg's own DBMS_LOCK.SLEEP rewrite loses
    (GAP-123): `pg_sleep(1);` -> `PERFORM pg_sleep(1);`, returning
    (fixed_source, number_of_fixes_applied).

    Mechanical: PL/pgSQL rejects a function called as a statement
    ('syntax error at or near "pg_sleep"', ora2pg 25.0 output loaded into
    PostgreSQL 16), and PERFORM is the one way to call it there --
    ora2pg's PLSQL.pm has that very rule, which its earlier bare rewrite
    shadows. Masked like the others, so a string or a comment is left
    alone."""
    from .pg_script import mask_literals

    masked = mask_literals(source)
    ends = [m.end() for m in _BARE_PG_SLEEP_RE.finditer(masked)]
    for at in reversed(ends):
        source = source[:at] + "PERFORM " + source[at:]
    return source, len(ends)

# Which mechanical fixes apply to which source dialect's generated output.
# Keyed by the same dialect names core.DIALECTS carries. MySQL has a
# single fix on purpose, not by oversight: `LIMIT a, b` (GAP-075) is pure
# syntax, but every other confirmed MySQL gap is either a construct ora2pg
# copies verbatim and whose correct replacement is a real design decision
# (ON DUPLICATE KEY UPDATE -> ON CONFLICT changes trigger/cascade
# behaviour; INSERT IGNORE -> ON CONFLICT DO NOTHING is narrower than
# IGNORE), or a loss that cannot be reconstructed from the generated
# output at all -- GAP-068's missing CREATE TYPE needs the enum values,
# which only exist in the MySQL source this file no longer is. Inventing a
# fix for those would be exactly the "rewriting DDL that's about to be
# deployed" this module's docstring rules out.
# What every fixer is: source in, (fixed source, number of fixes) out.
Fixer = Callable[[str], tuple[str, int]]

FIXERS_BY_DIALECT: dict[str, tuple[Fixer, ...]] = {
    "oracle": (fix_identity_double_parens, fix_recursive_with_keyword, fix_bare_pg_sleep),
    "mysql": (fix_mysql_limit_comma,),
    "mssql": (fix_mssql_charindex_quotes, fix_mssql_empty_declare),
}

# The detector whose gap each fix undoes. --load-check uses it to say
# "this statement failed to load, and --fix repairs it" with the right
# GAP number.
FIXER_DETECTOR: dict[Fixer, str] = {
    fix_identity_double_parens: "identity_column",
    fix_recursive_with_keyword: "recursive_with",
    fix_bare_pg_sleep: "dbms_sleep",
    fix_mysql_limit_comma: "mysql_limit_comma",
    fix_mssql_charindex_quotes: "mssql_charindex",
    fix_mssql_empty_declare: "mssql_parameterless_procedure",
}
