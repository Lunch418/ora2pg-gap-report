"""Shared, deliberately approximate PL/SQL lexical helpers.

Not a real parser — Oracle PL/SQL's full grammar is out of scope. What this
module does provide, and what detectors rely on for correctness: string- and
comment-aware masking (so keyword search never matches inside a literal or a
comment), and BEGIN/END block matching (so a routine's own executable
section can be told apart from a nested subprogram's).
"""

import re

# Oracle unquoted identifiers: letter, then letters/digits/_/$/#.
IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_$#]*"

# Oracle q-quote delimiter pairs (q'[...]', q'{...}', q'(...)' , q'<...>');
# any other non-alphanumeric char is its own closing delimiter (q'!...!').
_Q_QUOTE_PAIRS = {"[": "]", "{": "}", "(": ")", "<": ">"}

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


def mask_strings_and_comments(source: str) -> str:
    """Replace comment/string-literal contents with spaces, preserving
    length and newlines, so absolute offsets and line numbers stay valid
    and keyword regexes never match inside a literal or a comment."""
    out = []
    i, n = 0, len(source)
    while i < n:
        two = source[i : i + 2]
        if two == "--":
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if two == "/*":
            out.append("  ")
            i += 2
            while i < n and source[i : i + 2] != "*/":
                out.append("\n" if source[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append("  ")
                i += 2
            continue
        if source[i] in "nNqQ":
            open_pos = _q_quote_open_delim_pos(source, i)
            if open_pos is not None:
                open_delim = source[open_pos]
                close_delim = _Q_QUOTE_PAIRS.get(open_delim, open_delim)
                end = source.find(close_delim + "'", open_pos + 1)
                if end != -1:
                    for k in range(i, end + 2):
                        out.append("\n" if source[k] == "\n" else " ")
                    i = end + 2
                    continue
        if source[i] == "'":
            out.append(" ")
            i += 1
            while i < n:
                if source[i] == "'":
                    if source[i : i + 2] == "''":
                        out.append("  ")
                        i += 2
                        continue
                    out.append(" ")
                    i += 1
                    break
                out.append("\n" if source[i] == "\n" else " ")
                i += 1
            continue
        out.append(source[i])
        i += 1
    return "".join(out)


def line_at(text: str, pos: int) -> int:
    """1-indexed line number of `pos` within `text`."""
    return text.count("\n", 0, pos) + 1


def skip_balanced_parens(text: str, start: int) -> int:
    """`start` points at '('; returns the index just after the matching ')'."""
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)


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


def _own_is_as(text: str, name_end: int, hard_boundary: int):
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
    semi = text.find(";", pos)
    is_as = _IS_AS_RE.search(text, pos, hard_boundary)
    if is_as is None or (semi != -1 and semi < is_as.start()):
        return None
    return is_as


def _find_own_begin(text: str, is_as_end: int, hard_boundary: int, nested_spans: list):
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


def declare_and_begin(text: str, routine_name_end: int, hard_boundary: int):
    """Given the end of 'FUNCTION|PROCEDURE name', resolve THIS routine's
    own declare section — the span between its IS/AS and its own BEGIN —
    with any nested subprogram spans it contains called out separately so
    callers can exclude them. Returns None for forward declarations / specs
    with no body. Returns (declare_start, begin_pos, nested_spans)."""
    is_as = _own_is_as(text, routine_name_end, hard_boundary)
    if is_as is None:
        return None
    nested_spans: list = []
    begin_pos = _find_own_begin(text, is_as.end(), hard_boundary, nested_spans)
    if begin_pos is None:
        return None
    return is_as.end(), begin_pos, nested_spans


def own_declare_text(text: str, declare_start: int, begin_pos: int, nested_spans: list) -> str:
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


_PACKAGE_BODY_NAME_RE = re.compile(qualified_name_pattern(r"PACKAGE\s+BODY"), re.IGNORECASE)
# A standalone 'CREATE [OR REPLACE] PROCEDURE/FUNCTION name' — distinct from
# ROUTINE_START_RE, which only matches routines declared *inside* a package
# body ('PROCEDURE name IS', at the start of a line with no CREATE prefix).
_STANDALONE_ROUTINE_RE = re.compile(
    rf"CREATE\s+(?:OR\s+REPLACE\s+)?(?:FUNCTION|PROCEDURE)\s+({IDENTIFIER})",
    re.IGNORECASE,
)
_TRIGGER_NAME_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:EDITIONABLE\s+|NONEDITIONABLE\s+)?TRIGGER"),
    re.IGNORECASE,
)


def enclosing_object_name_index(text: str) -> list[tuple[int, str, str]]:
    """Every 'named container' start position in `text` (already masked),
    tagged by kind ('package' / 'nested_routine' / 'standalone_routine' /
    'trigger'), sorted by position. Build once per source file and pass to
    enclosing_object_name() for each finding — cheaper than re-scanning the
    whole file per finding, and keeps the attribution logic in one place
    instead of duplicated (and liable to silently diverge) across every
    detector that needs "which object contains this position"."""
    tagged = (
        [(m.start(), "package", m.group(1).upper()) for m in _PACKAGE_BODY_NAME_RE.finditer(text)]
        + [(m.start(), "nested_routine", m.group(1).upper()) for m in ROUTINE_START_RE.finditer(text)]
        + [(m.start(), "standalone_routine", m.group(1).upper()) for m in _STANDALONE_ROUTINE_RE.finditer(text)]
        + [(m.start(), "trigger", m.group(1).upper()) for m in _TRIGGER_NAME_RE.finditer(text)]
    )
    return sorted(tagged, key=lambda t: t[0])


def enclosing_object_name(index: list[tuple[int, str, str]], position: int) -> str:
    """Best-effort 'what named object contains this position': a
    PACKAGE_BODY.ROUTINE for something nested inside a package, a bare
    standalone routine/trigger name, or a bare package name if only a
    package (not yet inside any of its own routines) precedes it. 'UNKNOWN'
    if nothing precedes at all — e.g. a construct in a bare anonymous block
    with no enclosing named object.

    package/standalone_routine/trigger are treated as mutually exclusive
    top-level containers: whichever one starts most recently is "current",
    and starting a new one implicitly ends the previous one (mirroring
    compound_triggers.py's "bounded by the next CREATE TRIGGER" — a
    standalone routine or trigger can't itself be inside a package body, so
    its start must mean any earlier package's scope has ended). Without
    this, a package's name would otherwise leak into a later, unrelated
    standalone routine or trigger's own nested finds. There is deliberately
    no explicit "package body's own END" tracking — this module's actual
    input is DBMS_METADATA.GET_DDL-exported object DDL (PACKAGE BODY /
    TRIGGER / standalone PROCEDURE/FUNCTION definitions), which never
    contains free-standing anonymous PL/SQL blocks between them; a
    theoretical anonymous block right after a package body and before the
    next named object would still (incorrectly) inherit that package's
    name, but that shape of input is outside this tool's actual scope."""
    package_name = None
    leaf: tuple[str, bool] | None = None  # (name, needs_package_prefix)
    for pos, kind, name in index:
        if pos > position:
            break
        if kind == "package":
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
