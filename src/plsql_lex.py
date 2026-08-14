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
        nested_is_as = _IS_AS_RE.search(text, nested.end(), hard_boundary)
        if not nested_is_as:
            return None
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
    pos = routine_name_end
    while pos < hard_boundary and text[pos] in " \t\r\n":
        pos += 1
    if pos < hard_boundary and text[pos] == "(":
        pos = skip_balanced_parens(text, pos)
    is_as = _IS_AS_RE.search(text, pos, hard_boundary)
    if not is_as:
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
