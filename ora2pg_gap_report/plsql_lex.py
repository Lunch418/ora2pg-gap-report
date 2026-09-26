"""Shared, deliberately approximate PL/SQL lexical helpers.

Not a real parser — Oracle PL/SQL's full grammar is out of scope. What this
module does provide, and what detectors rely on for correctness: string- and
comment-aware masking (so keyword search never matches inside a literal or a
comment), and BEGIN/END block matching (so a routine's own executable
section can be told apart from a nested subprogram's).
"""

import re
from functools import lru_cache
from .lex_common import (
    line_at,
    skip_balanced_parens,
    table_column_definition_list,
)

# Oracle unquoted identifiers: letter, then letters/digits/_/$/#.
IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_$#]*"

# Oracle q-quote delimiter pairs (q'[...]', q'{...}', q'(...)' , q'<...>');
# any other non-alphanumeric char is its own closing delimiter (q'!...!').
_Q_QUOTE_PAIRS = {"[": "]", "{": "}", "(": ")", "<": ">"}

# SQL*Plus's REM/REMARK line comment -- distinct from '--' in that it's
# only a comment when REM/REMARK is the first token on its own line ('x :=
# rem_var;' keeps REM as an ordinary identifier prefix, not a comment).
# The lookahead requires REM/REMARK to be followed by whitespace/EOL/EOF,
# so a real identifier like REMOTE_TABLE never matches.
_REM_RE = re.compile(r"REM(?:ARK)?(?=[ \t\r\n]|\Z)", re.IGNORECASE)


def _at_line_start(source: str, i: int) -> bool:
    """True if `i` is preceded only by same-line horizontal whitespace
    back to the start of a line (or of the text) -- i.e. `i` is where the
    first real token on its line begins."""
    j = i
    while j > 0 and source[j - 1] in " \t":
        j -= 1
    return j == 0 or source[j - 1] == "\n"

ROUTINE_START_RE = re.compile(
    rf"^\s*(?:FUNCTION|PROCEDURE)\s+({IDENTIFIER})",
    re.IGNORECASE | re.MULTILINE,
)


def qualified_name_pattern(keyword_pattern: str) -> str:
    """Regex source fragment matching `<keyword> [schema.]name`, capturing
    the (possibly quoted) final name component. Does not verify that a
    leading quote is matched by a trailing one — good enough for name
    extraction, not for validating well-formedness."""
    return rf'{keyword_pattern}\s+(?:"?{IDENTIFIER}"?\.)?"?({IDENTIFIER})"?'
_IS_AS_RE = re.compile(r"\b(?:IS|AS)\b", re.IGNORECASE)
_BEGIN_RE = re.compile(r"\bBEGIN\b", re.IGNORECASE)
_BLOCK_TOKEN_RE = re.compile(
    r"\bBEGIN\b|\bCASE\b|\bIF\b|\bLOOP\b"
    r"|\bEND\s+LOOP\b|\bEND\s+IF\b|\bEND\s+CASE\b|\bEND\b",
    re.IGNORECASE,
)
# Tokens that open a block whose matching close is its own qualified END form.
_QUALIFIED_CLOSERS = {"END LOOP": "LOOP", "END IF": "IF", "END CASE": "CASE"}


def _q_quote_open_delim_pos(source: str, i: int) -> int | None:
    """If source[i:] starts an Oracle q-quote literal (q'...' or nq'...',
    case-insensitive, not part of a larger identifier), return the index of
    its opening delimiter character; else None."""
    n = len(source)
    if i > 0 and (source[i - 1].isalnum() or source[i - 1] == "_"):
        return None
    j = i
    if j < n and source[j] in "nN":
        j += 1
    if j < n and source[j] in "qQ" and source[j + 1 : j + 2] == "'" and j + 2 < n:
        return j + 2
    return None


# Requires plain whitespace between the two keywords -- like every other
# keyword-pair regex in this module (e.g. _BULK_COLLECT_RE's "BULK\s+COLLECT"
# in bulk_collect.py), a comment wedged between EXECUTE and IMMEDIATE
# defeats the match and that EXECUTE IMMEDIATE's argument stays masked, same
# as before this function existed. Not treated as a bug to chase here: it's
# the same pre-existing, project-wide tradeoff of pattern matching over a
# real parser, not something unique to dynamic-SQL visibility, and it fails
# safe (falls back to the old fully-masked behavior, not a false positive).
_EXEC_IMMEDIATE_RE = re.compile(r"\bEXECUTE\s+IMMEDIATE\b", re.IGNORECASE)


# Where _mask() has something to decide. Everywhere else a character is
# copied through unchanged, so the text between two matches can be copied
# as one chunk -- which is what makes masking a large file fast. Each
# alternative is a superset of the condition its branch in _mask() checks
# (e.g. REM is found anywhere, and the branch still checks it opens its
# line), never a subset, so no position a branch would act on is skipped.
_MASK_CANDIDATE_SOURCE = r"--|/\*|'|[nN]?[qQ]'|(?i:REM(?:ARK)?)(?=[ \t\r\n]|\Z)"
_MASK_CANDIDATES = re.compile(_MASK_CANDIDATE_SOURCE)
_MASK_CANDIDATES_IN_DYNAMIC_SQL = re.compile(_MASK_CANDIDATE_SOURCE + "|;")
_MASK_CANDIDATES_BEFORE_DYNAMIC_SQL = re.compile(
    _MASK_CANDIDATE_SOURCE + r"|(?i:\bEXECUTE\s+IMMEDIATE\b)"
)
# The body of a '...' literal after its opening quote: anything but a
# quote, or a doubled '' (an escaped quote). Ends at the closing quote,
# or at the end of the text for an unterminated literal.
_STRING_BODY_RE = re.compile(r"[^']*(?:''[^']*)*")
_NOT_NEWLINE_RE = re.compile(r"[^\n]")


def _blank(text: str) -> str:
    """`text` with every character but a newline replaced by a space --
    what masking does to a comment or a literal, keeping both the length
    and the line numbers of everything after it."""
    return _NOT_NEWLINE_RE.sub(" ", text)


def _mask(source: str, reveal_dynamic_sql: bool, reveal_strings: bool = False) -> str:
    """Shared tokenizer for mask_strings_and_comments(),
    mask_dynamic_sql_visible() and mask_comments_only() -- all three views
    must agree on exactly where every comment/string/q-quote starts and
    ends, or their "same length, valid offsets in every view" contract
    (every dynamic-SQL-aware detector relies on it) could silently break
    if one view's rules drifted from another's under a future fix.
    `reveal_dynamic_sql=False` reproduces mask_strings_and_comments()
    exactly: `in_dynamic_sql` can never become True, so every branch below
    that checks it takes its "mask" side. `reveal_strings=True` keeps
    literal *content* -- ordinary and q-quoted alike -- while still
    blanking comments, for the two detectors whose subject matter is the
    literal itself (a q'...' literal, a 'RR' date format model)."""
    out: list[str] = []
    i, n = 0, len(source)
    in_dynamic_sql = False
    while i < n:
        # Jump straight to the next position where anything below could
        # apply, copying the plain text in between as one chunk. Every
        # branch that follows is still evaluated at that position exactly
        # as it was per character before; the candidate patterns only
        # skip positions where all of them would have fallen through to
        # the plain append at the bottom. Which pattern depends on the
        # state, because two branches only exist in some states.
        if in_dynamic_sql:
            candidates = _MASK_CANDIDATES_IN_DYNAMIC_SQL
        elif reveal_dynamic_sql:
            candidates = _MASK_CANDIDATES_BEFORE_DYNAMIC_SQL
        else:
            candidates = _MASK_CANDIDATES
        found = candidates.search(source, i)
        if found is None:
            out.append(source[i:])
            break
        if found.start() > i:
            out.append(source[i : found.start()])
            i = found.start()
        if reveal_dynamic_sql and not in_dynamic_sql and source[i].upper() == "E":
            m = _EXEC_IMMEDIATE_RE.match(source, i)
            if m:
                out.append(source[i : m.end()])
                i = m.end()
                in_dynamic_sql = True
                continue
        two = source[i : i + 2]
        if two == "--" or (
            source[i] in "rR" and _at_line_start(source, i) and _REM_RE.match(source, i)
        ):
            line_end = source.find("\n", i)
            if line_end == -1:
                line_end = n
            out.append(" " * (line_end - i))
            i = line_end
            continue
        if two == "/*":
            close = source.find("*/", i + 2)
            body_end = close if close != -1 else n
            out.append("  " + _blank(source[i + 2 : body_end]))
            if close != -1:
                out.append("  ")
                i = close + 2
            else:
                i = n
            continue
        if source[i] in "nNqQ":
            open_pos = _q_quote_open_delim_pos(source, i)
            if open_pos is not None:
                open_delim = source[open_pos]
                close_delim = _Q_QUOTE_PAIRS.get(open_delim, open_delim)
                end = source.find(close_delim + "'", open_pos + 1)
                if end != -1:
                    literal = source[i : end + 2]
                    out.append(literal if in_dynamic_sql or reveal_strings else _blank(literal))
                    i = end + 2
                    continue
        if source[i] == "'":
            reveal = in_dynamic_sql or reveal_strings
            # A doubled '' inside the literal is an escaped quote, not its
            # end; the literal runs to the first single ' after that, or to
            # the end of the text if it never closes.
            body_match = _STRING_BODY_RE.match(source, i + 1)
            assert body_match is not None  # every alternative can match empty
            close = body_match.end()
            body = source[i + 1 : close]
            out.append("'" if reveal else " ")
            out.append(body if reveal else _blank(body))
            if close < n:
                out.append("'" if reveal else " ")
                i = close + 1
            else:
                i = n
            continue
        if source[i] == ";" and in_dynamic_sql:
            in_dynamic_sql = False
        out.append(source[i])
        i += 1
    return "".join(out)


@lru_cache(maxsize=8)
def mask_strings_and_comments(source: str) -> str:
    """Replace comment/string-literal contents with spaces, preserving
    length and newlines, so absolute offsets and line numbers stay valid
    and keyword regexes never match inside a literal or a comment.

    Cached: every one of this project's ~37 detectors calls this with the
    exact same `source` for a given scanned file (confirmed: none mutate
    their `clean`/`visible` string result, which is impossible anyway --
    Python strings are immutable), so scanning one file used to redo this
    same O(n) masking pass ~37 times over. maxsize=8 is deliberately
    small -- within one scan_source() call there's only ever one distinct
    `source` in flight, so a cache of 1 would already collapse the
    redundancy; 8 just adds headroom (e.g. a long-running --tui session
    re-scanning a small, recently-touched set of files) without letting a
    long session's cache grow unbounded and hold arbitrarily many past
    files' full text in memory forever."""
    return _mask(source, reveal_dynamic_sql=False)


@lru_cache(maxsize=8)
def mask_dynamic_sql_visible(source: str) -> str:
    """Like mask_strings_and_comments(), but string-literal content that is
    (part of) an EXECUTE IMMEDIATE argument -- from right after the keyword
    to the next bare ';' outside any literal -- is left visible instead of
    blanked, so a gap-triggering construct built as dynamic SQL/PL-SQL text
    (a single literal or a '...' || expr || '...' concatenation) is still
    detectable by keyword search. Comments and non-dynamic-SQL string
    literals are masked exactly as before.

    This is deliberately a SEPARATE masked view, not a replacement for
    mask_strings_and_comments(). A detector that needs "what named object
    contains this position" (enclosing_object_name_index()) must still
    build that index from the safe, fully-masked view: dynamic SQL that
    itself creates a package/procedure at runtime (real example: utPLSQL's
    test suite dynamically creating a package via EXECUTE IMMEDIATE) would
    otherwise be picked up as if it were a real container declared in the
    source tree, corrupting attribution for unrelated findings. Only a
    detector's own keyword-matching regex should run against this visible
    view; positions found in it remain valid lookups into an index built
    from the safe view, since masking never changes length or newlines in
    either view.

    Cached -- see mask_strings_and_comments()'s own docstring for why."""
    return _mask(source, reveal_dynamic_sql=True)


@lru_cache(maxsize=8)
def mask_comments_only(source: str) -> str:
    """Blank out comments but leave string-literal content -- ordinary
    and q-quoted alike -- exactly as written.

    The mirror image of the other two views, and needed for the same
    reason they are: a detector must never match inside a comment. But
    two gaps are *about* the literal itself rather than about code around
    it -- Oracle's q'...' alternative quoting (GAP-062) and an 'RR' code
    inside a TO_DATE format model (GAP-058) -- and both views above blank
    precisely the text those two need to see. Scanning the raw source
    instead would work but would also match commented-out code, which is
    the one thing every detector here is careful not to do.

    Same length- and newline-preserving contract as the other two views,
    produced by the same tokenizer, so offsets found here stay valid for
    line_at() and enclosing_object_name_index() built from the safe view.

    Cached -- see mask_strings_and_comments()'s own docstring for why."""
    return _mask(source, reveal_dynamic_sql=False, reveal_strings=True)


def find_matching_end(text: str, begin_pos: int, hard_boundary: int) -> int | None:
    """Given the index of a BEGIN token, find the index just past the ';'
    of its matching bare END, tracking nested BEGIN/CASE/IF/LOOP blocks.
    A bare END closes a BEGIN block or a CASE *expression* (both use plain
    END in Oracle); END LOOP/IF/CASE close their own qualified opener.
    """
    stack = ["BEGIN"]
    pos = begin_pos + len("BEGIN")
    for m in _BLOCK_TOKEN_RE.finditer(text, pos, hard_boundary):
        token = re.sub(r"\s+", " ", m.group(0).upper())
        if token in ("BEGIN", "CASE", "IF", "LOOP"):
            stack.append(token)
            continue
        expected = _QUALIFIED_CLOSERS.get(token)
        if expected is not None:
            if stack and stack[-1] == expected:
                stack.pop()
        else:  # bare END
            if stack:
                stack.pop()
        if not stack:
            semi = text.find(";", m.end())
            return semi + 1 if semi != -1 and semi < hard_boundary else m.end()
    return None


def _own_is_as(text: str, name_end: int, hard_boundary: int) -> re.Match[str] | None:
    """The IS/AS match belonging to the routine whose name ends at
    `name_end`, or None if this is a forward declaration ('PROCEDURE
    helper;', used to allow mutual recursion between subprograms) rather
    than a real definition. A forward declaration has no IS/AS of its own —
    a bare ';' terminates its signature first — so searching forward
    unconditionally would find some later, unrelated routine's IS/AS
    instead (commonly the real body of this same forward-declared name),
    misattributing everything in between (including sibling declarations
    like a PRAGMA) to it."""
    pos = name_end
    while pos < hard_boundary and text[pos] in " \t\r\n":
        pos += 1
    if pos < hard_boundary and text[pos] == "(":
        pos = skip_balanced_parens(text, pos)
    # Search only up to this signature's own ';'. An IS/AS past it belongs
    # to something else anyway, and searching on to hard_boundary made
    # every bodiless declaration in a package spec rescan the rest of the
    # file -- quadratic in the number of declarations. ';' is not a word
    # character, so \b behaves the same at the cut as it did in the text.
    semi = text.find(";", pos, hard_boundary)
    return _IS_AS_RE.search(text, pos, semi if semi != -1 else hard_boundary)


def _find_own_begin(
    text: str, is_as_end: int, hard_boundary: int, nested_spans: list[tuple[int, int]]
) -> int | None:
    """Return the index of the BEGIN starting THIS routine's own body,
    recursively skipping any nested subprogram declarations found first
    (recording their [start, end) spans in `nested_spans`)."""
    cursor = is_as_end
    while True:
        nested = ROUTINE_START_RE.search(text, cursor, hard_boundary)
        begin = _BEGIN_RE.search(text, cursor, hard_boundary)
        if not begin:
            return None
        if not nested or begin.start() < nested.start():
            return begin.start()
        nested_is_as = _own_is_as(text, nested.end(), hard_boundary)
        if nested_is_as is None:
            # Forward declaration, not a definition — nothing to recurse
            # into here; skip past its own ';' and keep scanning.
            semi = text.find(";", nested.end())
            if semi == -1 or semi >= hard_boundary:
                return None
            cursor = semi + 1
            continue
        nested_begin = _find_own_begin(text, nested_is_as.end(), hard_boundary, nested_spans)
        if nested_begin is None:
            return None
        nested_end = find_matching_end(text, nested_begin, hard_boundary)
        if nested_end is None:
            return None
        nested_spans.append((nested.start(), nested_end))
        cursor = nested_end


def declare_and_begin(
    text: str, routine_name_end: int, hard_boundary: int
) -> tuple[int, int, list[tuple[int, int]]] | None:
    """Given the end of 'FUNCTION|PROCEDURE name', resolve THIS routine's
    own declare section — the span between its IS/AS and its own BEGIN —
    with any nested subprogram spans it contains called out separately so
    callers can exclude them. Returns None for forward declarations / specs
    with no body. Returns (declare_start, begin_pos, nested_spans)."""
    is_as = _own_is_as(text, routine_name_end, hard_boundary)
    if is_as is None:
        return None
    nested_spans: list[tuple[int, int]] = []
    begin_pos = _find_own_begin(text, is_as.end(), hard_boundary, nested_spans)
    if begin_pos is None:
        return None
    return is_as.end(), begin_pos, nested_spans


def own_declare_text(text: str, declare_start: int, begin_pos: int, nested_spans: list[tuple[int, int]]) -> str:
    """The routine's own declare-section text, with any nested subprogram
    spans blanked out (so a nested routine's own PRAGMA/content is not
    mistaken for this routine's)."""
    chars = list(text[declare_start:begin_pos])
    for start, end in nested_spans:
        lo, hi = max(start, declare_start), min(end, begin_pos)
        for i in range(lo, hi):
            if chars[i - declare_start] != "\n":
                chars[i - declare_start] = " "
    return "".join(chars)


_CREATE_PREFIX = r"CREATE\s+(?:OR\s+REPLACE\s+)?"
_EDITIONABLE_PREFIX = r"(?:EDITIONABLE\s+|NONEDITIONABLE\s+)?"
PACKAGE_BODY_NAME_RE = re.compile(
    qualified_name_pattern(_CREATE_PREFIX + _EDITIONABLE_PREFIX + r"PACKAGE\s+BODY"), re.IGNORECASE
)
# A package *spec* ('CREATE [OR REPLACE] PACKAGE name IS/AS ...', no BODY
# keyword) — found missing findings-attribution-wise by scanning a large
# real-world PL/SQL corpus (alexandria-plsql-utils): a package spec can
# itself declare a local collection TYPE (bulk_collect.py's target) as
# part of its public interface, and every such finding was silently
# falling back to object_name='UNKNOWN' because only PACKAGE BODY was
# recognized as a 'package' container here. The negative lookahead is
# what keeps this from double-matching a real 'PACKAGE BODY name'
# occurrence (already handled by PACKAGE_BODY_NAME_RE above) as a
# second, spurious 'package' entry at the same position.
PACKAGE_SPEC_NAME_RE = re.compile(
    qualified_name_pattern(_CREATE_PREFIX + _EDITIONABLE_PREFIX + r"PACKAGE(?!\s+BODY\b)"), re.IGNORECASE
)
# A standalone 'CREATE [OR REPLACE] PROCEDURE/FUNCTION name' — distinct from
# ROUTINE_START_RE, which only matches routines declared *inside* a package
# body ('PROCEDURE name IS', at the start of a line with no CREATE prefix).
STANDALONE_ROUTINE_RE = re.compile(
    _CREATE_PREFIX + rf"(?:FUNCTION|PROCEDURE)\s+({IDENTIFIER})",
    re.IGNORECASE,
)
_TRIGGER_NAME_RE = re.compile(
    qualified_name_pattern(_CREATE_PREFIX + _EDITIONABLE_PREFIX + r"TRIGGER"),
    re.IGNORECASE,
)
# A view can itself contain a gap-triggering construct in its own SELECT
# (e.g. JSON_TABLE, PIVOT, MODEL) — found via a real-world corpus
# (oracle-samples/db-sample-schemas: customer_orders/co_create.sql, a
# JSON_TABLE call inside CREATE OR REPLACE VIEW). Without this, any such
# finding silently fell back to object_name='UNKNOWN' since a view was
# never a recognized attribution container at all. MATERIALIZED is
# included too — same reasoning, a materialized view's defining query can
# contain the same constructs.
_VIEW_NAME_RE = re.compile(
    qualified_name_pattern(
        _CREATE_PREFIX
        + r"(?:FORCE\s+|NOFORCE\s+)?"
        + _EDITIONABLE_PREFIX
        + r"(?:MATERIALIZED\s+)?VIEW"
    ),
    re.IGNORECASE,
)


# No \A/^ anchor needed: Pattern.match(text, boundary, create_pos) already
# only attempts a match starting exactly at `boundary` -- \A would be
# actively wrong here, since \A always refers to index 0 of the whole
# string regardless of the pos argument, not to `boundary`.
_GRANT_OR_REVOKE_RE = re.compile(r"\s*(?:GRANT|REVOKE)\b", re.IGNORECASE)

# SQL*Plus's own terminator: '/' alone on its line runs the buffer, so in
# a script it ends whatever object was being created. Only on a line of
# its own -- SQL*Plus itself treats nothing else as the terminator, which
# is why a division operator is never written that way.
_SQLPLUS_SLASH_RE = re.compile(r"^[ \t]*/[ \t\r]*$", re.MULTILINE)


def is_inside_grant_or_revoke_statement(text: str, create_pos: int) -> bool:
    """True if the 'CREATE' at create_pos is part of an *enclosing*
    GRANT/REVOKE statement's privilege list ('GRANT CREATE SESSION,
    CREATE SYNONYM, CREATE VIEW TO oe;', a real line from
    oracle-samples/db-sample-schemas) rather than a genuine 'CREATE VIEW
    name AS ...' declaration. Without this, qualified_name_pattern would
    happily capture whatever word follows that phantom 'CREATE VIEW'
    (here, the grantee-introducing keyword 'TO') as if it were a real
    object name, corrupting attribution for everything between it and the
    next real declaration.

    Deliberately does NOT require CREATE to be the very first token of
    its own statement (an earlier version of this check did, and that
    broke on real input: SQL*Plus client commands -- PROMPT, SET ...,
    @script, DEFINE, WHENEVER -- routinely precede a real CREATE and are
    themselves terminated by a bare newline, not ';' or '/', which made
    that stricter check wrongly reject genuine declarations, verified via
    oracle-samples/db-sample-schemas/human_resources/hr_code.sql's
    'SET ECHO OFF' immediately before 'CREATE OR REPLACE PROCEDURE
    secure_dml'). Instead, this looks at the *enclosing statement* --
    bounded by the nearest preceding ';'/'/' or start-of-text, which is
    where a GRANT/REVOKE statement itself reliably starts -- and checks
    whether that statement's own first word is GRANT or REVOKE."""
    boundary = max(text.rfind(";", 0, create_pos), text.rfind("/", 0, create_pos)) + 1
    return bool(_GRANT_OR_REVOKE_RE.match(text, boundary, create_pos))


@lru_cache(maxsize=8)
def enclosing_object_name_index(text: str) -> tuple[tuple[int, str, str], ...]:
    """Every 'named container' start position in `text` (already masked),
    tagged by kind ('package' / 'nested_routine' / 'standalone_routine' /
    'trigger' / 'view'), sorted by position. Build once per source file
    and pass to enclosing_object_name() for each finding — cheaper than
    re-scanning the whole file per finding, and keeps the attribution
    logic in one place instead of duplicated (and liable to silently
    diverge) across every detector that needs "which object contains this
    position".

    Cached (see mask_strings_and_comments()'s own docstring) -- roughly a
    third of this project's detectors call this with the same masked
    `text` for a given scanned file. A tuple, not a list: every caller
    only ever reads it (confirmed -- no .append()/.sort()/similar
    anywhere in this codebase), and returning an immutable value from a
    cache makes that a property the type system enforces, not just one
    true today -- a future caller that tried to mutate a cached list
    in place would otherwise silently corrupt every other caller sharing
    that same cache entry."""
    # ROUTINE_START_RE has no CREATE prefix (it matches a nested routine
    # declared *inside* a package body, e.g. 'PROCEDURE name IS' at the
    # start of a line), so it isn't subject to the GRANT/REVOKE check
    # below — only the CREATE-anchored regexes need it, to reject a
    # GRANT/REVOKE statement's privilege list ('GRANT ..., CREATE VIEW
    # TO ...') matching as if it were a real declaration.
    tagged = (
        [
            (m.start(), "package", m.group(1).upper())
            for m in PACKAGE_BODY_NAME_RE.finditer(text)
            if not is_inside_grant_or_revoke_statement(text, m.start())
        ]
        + [
            (m.start(), "package", m.group(1).upper())
            for m in PACKAGE_SPEC_NAME_RE.finditer(text)
            if not is_inside_grant_or_revoke_statement(text, m.start())
        ]
        + [(m.start(), "nested_routine", m.group(1).upper()) for m in ROUTINE_START_RE.finditer(text)]
        + [
            (m.start(), "standalone_routine", m.group(1).upper())
            for m in STANDALONE_ROUTINE_RE.finditer(text)
            if not is_inside_grant_or_revoke_statement(text, m.start())
        ]
        + [
            (m.start(), "trigger", m.group(1).upper())
            for m in _TRIGGER_NAME_RE.finditer(text)
            if not is_inside_grant_or_revoke_statement(text, m.start())
        ]
        + [
            (m.start(), "view", m.group(1).upper())
            for m in _VIEW_NAME_RE.finditer(text)
            if not is_inside_grant_or_revoke_statement(text, m.start())
        ]
        # Not a container: where the previous one ends. See
        # enclosing_object_name().
        + [(m.start(), "end", "") for m in _SQLPLUS_SLASH_RE.finditer(text)]
    )
    return tuple(sorted(tagged, key=lambda t: t[0]))


def enclosing_object_name(index: tuple[tuple[int, str, str], ...], position: int) -> str:
    """Best-effort 'what named object contains this position': a
    PACKAGE_BODY.ROUTINE for something nested inside a package, a bare
    standalone routine/trigger/view name, or a bare package name if only a
    package (not yet inside any of its own routines) precedes it. 'UNKNOWN'
    if nothing precedes at all — e.g. a construct in a bare anonymous block
    with no enclosing named object.

    package/standalone_routine/trigger/view are treated as mutually
    exclusive top-level containers: whichever one starts most recently is
    "current", and starting a new one implicitly ends the previous one
    (mirroring compound_triggers.py's "bounded by the next CREATE TRIGGER"
    — none of these can itself be inside a package body, so its start must
    mean any earlier package's scope has ended). Without this, a package's
    name would otherwise leak into a later, unrelated standalone routine,
    trigger, or view's own nested finds.

    An object also ends at SQL*Plus's '/' terminator (an "end" entry in
    the index). Deployment scripts -- the install scripts of every real
    project this was checked against -- put one after each object and
    follow it with anonymous blocks, data fixes and grants; without the
    marker those were all reported as part of the last routine declared
    (an INSERT ALL in OOS-Utils' data block came out as
    OOS_UTIL_WEB.DOWNLOAD_FILE). After a '/', a finding belongs to no
    object until the next CREATE. There is still no tracking of a package
    body's own END: DBMS_METADATA.GET_DDL output has no '/' at all, and
    between two of its objects there is nothing to misattribute."""
    package_name = None
    leaf: tuple[str, bool] | None = None  # (name, needs_package_prefix)
    for pos, kind, name in index:
        if pos > position:
            break
        if kind == "end":
            package_name = None
            leaf = None
        elif kind == "package":
            package_name = name
            leaf = None
        else:
            if kind != "nested_routine":
                package_name = None  # a standalone routine/trigger can't be inside a package
            leaf = (name, kind == "nested_routine")
    if leaf:
        name, needs_prefix = leaf
        return f"{package_name}.{name}" if needs_prefix and package_name else name
    return package_name or "UNKNOWN"


def statement_end(text: str, search_from: int, next_match_start: int | None) -> int:
    """End of a schema-level DDL statement (CREATE TABLE/INDEX/... and
    similar) starting at or before `search_from`: the next ';', or
    `next_match_start` (the start position of the next occurrence of the
    same kind of statement, if the caller is iterating over one regex's
    matches and knows it) -- whichever comes first -- or the end of
    `text` if neither is found.

    Exists because DBMS_METADATA.GET_DDL's default output (this project's
    documented Oracle export mechanism -- see oracle_connector.py) has no
    trailing ';': SQLTERMINATOR is off unless the caller explicitly turns
    it on. A detector that scopes "this statement's own text" to just
    "up to the next ';', or end of file if none" silently swallows every
    later statement in the file into the first unterminated one once that
    happens -- confirmed to actually happen with real unterminated
    DBMS_METADATA-style output, misattributing a later table's own
    findings to an earlier, unrelated table. Bounding by the next
    same-kind statement's own start (when the caller has it) closes that
    hole even with no ';' anywhere: once a second 'CREATE TABLE' (or
    whatever kind is being scanned) begins, the first one's statement is
    over regardless of punctuation."""
    semi = text.find(";", search_from)
    candidates = [c for c in (semi if semi != -1 else None, next_match_start) if c is not None]
    return min(candidates) if candidates else len(text)



# Re-exported so a detector keeps importing everything it needs from its
# own dialect's lexer: which of these are dialect-independent is an
# implementation detail of the lexers, not something 106 detectors and
# the detector factory should each have to know.
__all__ = [  # noqa: RUF022  -- grouped by what the name is for, not alphabetically
    "IDENTIFIER",
    "qualified_name_pattern",
    "mask_strings_and_comments",
    "mask_dynamic_sql_visible",
    "mask_comments_only",
    "line_at",
    "skip_balanced_parens",
    "table_column_definition_list",
    "enclosing_object_name_index",
    "enclosing_object_name",
    "statement_end",
    "declare_and_begin",
    "own_declare_text",
    "find_matching_end",
    "is_inside_grant_or_revoke_statement",
]
