import re
from functools import lru_cache

from ..models import Finding
from ..plsql_lex import IDENTIFIER, line_at, mask_strings_and_comments, skip_balanced_parens

# Oracle-supplied packages: the DBMS_/UTL_ families, the PL/SQL Web Toolkit
# (HTP, OWA, OWA_UTIL, ...), APEX and Oracle Text.
_SUPPLIED = r"DBMS_[A-Za-z0-9_$#]*|UTL_[A-Za-z0-9_$#]*|HTP|OWA(?:_[A-Za-z0-9_$#]*)?|APEX_[A-Za-z0-9_$#]*|CTX_[A-Za-z0-9_$#]*"
# A procedure called as a statement: a supplied package's name, not part
# of a longer name, followed by its arguments or straight by the `;` --
# and, checked by looking back (see statement_calls), at the start of a
# statement. Finding the names first and looking back is much faster on a
# large file than trying the statement-start alternatives everywhere.
STATEMENT_CALL_RE = re.compile(
    rf"(?<![A-Za-z0-9_$#.])((?:SYS\s*\.\s*)?({_SUPPLIED})\s*\.\s*({IDENTIFIER}))\s*(?=[(;])",
    re.IGNORECASE,
)
# The supplied packages' names start with one of these; finding them by
# plain substring search and matching only there is far faster on a large
# file than letting the regex try every position.
_PREFIXES = ("DBMS_", "UTL_", "HTP", "OWA", "APEX_", "CTX_")
_SYS_BEFORE_RE = re.compile(r"(?<![A-Za-z0-9_$#.])SYS\s*\.\s*\Z", re.IGNORECASE)
_STATEMENT_KEYWORD_RE = re.compile(r"\b(?:BEGIN|THEN|ELSE|LOOP)\Z", re.IGNORECASE)


def _at_statement_start(clean: str, pos: int) -> bool:
    """Whether `pos` starts a statement: what precedes it, past any
    whitespace (masked comments included, however long), is a `;` or one
    of BEGIN, THEN, ELSE, LOOP."""
    i = pos - 1
    while i >= 0 and clean[i].isspace():
        i -= 1
    if i < 0:
        return False
    if clean[i] == ";":
        return True
    return _STATEMENT_KEYWORD_RE.search(clean, max(0, i - 6), i + 1) is not None

# What ora2pg 25.0 does convert at statement level (PLSQL.pm): DBMS_OUTPUT's
# printing (RAISE NOTICE) and ENABLE (commented out); SLEEP is GAP-123's;
# DBMS_SQL's open/parse/execute sequence is rewritten into EXECUTE as a
# whole; DBMS_STANDARD.RAISE EXCEPTION.
_CONVERTED_RE = re.compile(
    r"^(?:DBMS_OUTPUT\.(?:PUT_LINE|PUT|NEW_LINE|ENABLE)|DBMS_(?:LOCK|SESSION)\.SLEEP|DBMS_SQL\.\w+|DBMS_STANDARD\.\w+)$",
    re.IGNORECASE,
)


@lru_cache(maxsize=4)
def statement_calls(clean: str) -> tuple[re.Match[str], ...]:
    """Every call of a supplied-package procedure as a statement in masked
    `clean`, whether ora2pg converts it or not. Cached: three detectors
    (this one, dbms_sleep, dbms_utl_calls) ask for the same text."""
    upper = clean.upper()
    starts: set[int] = set()
    for prefix in _PREFIXES:
        at = upper.find(prefix)
        while at != -1:
            starts.add(at)
            at = upper.find(prefix, at + 1)
    calls = []
    for start in sorted(starts):
        # A SYS. in front belongs to the call: start the match there.
        sys = _SYS_BEFORE_RE.search(clean, max(0, start - 16), start)
        m = STATEMENT_CALL_RE.match(clean, sys.start() if sys else start)
        if m is None or not _at_statement_start(clean, m.start()):
            continue
        after = m.end()
        if clean[after] == "(":
            after = skip_balanced_parens(clean, after)
        if clean[after:].lstrip().startswith(";"):
            calls.append(m)
    return tuple(calls)


def find_supplied_package_call(source: str) -> list[Finding]:
    """Detect a procedure of an Oracle-supplied package called as a
    statement that ora2pg leaves as it is: `DBMS_APPLICATION_INFO.SET_MODULE
    ('m', 'a');`, `DBMS_STATS.GATHER_TABLE_STATS(USER, 'T');`,
    `UTL_FILE.FCLOSE_ALL;`, `HTP.P('x');`, `DBMS_OUTPUT.DISABLE;`.

    ora2pg 25.0 writes `CALL pkg.proc(...)` only for procedures of packages
    in the same run; anything else it copies, and PL/pgSQL has no bare
    procedure-call statement -- the whole routine is rejected at load time
    ('syntax error at or near "DBMS_APPLICATION_INFO"'), whether or not a
    replacement for the package exists in PostgreSQL. Oracle 23ai compiles
    and runs the original. Found in OraOpenSource Logger (htp.p).
    dbms_utl_calls reports the other, non-statement uses. See
    docs/research/gap-122-supplied-package-call.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []
    for m in statement_calls(clean):
        name = f"{m.group(2)}.{m.group(3)}".upper()
        if _CONVERTED_RE.match(name):
            continue
        findings.append(
            Finding(
                detector="supplied_package_call",
                severity="high",
                object_name=name,
                line=line_at(clean, m.start(1)),
                snippet=name,
                message_id="supplied_package_call",
            )
        )
    return findings
