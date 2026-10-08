import re

from ..models import Finding
from ..plsql_lex import IDENTIFIER, line_at, mask_strings_and_comments, skip_balanced_parens

# Oracle-supplied packages: the DBMS_/UTL_ families, the PL/SQL Web Toolkit
# (HTP, OWA, OWA_UTIL, ...), APEX and Oracle Text.
_SUPPLIED = r"DBMS_[A-Za-z0-9_$#]*|UTL_[A-Za-z0-9_$#]*|HTP|OWA(?:_[A-Za-z0-9_$#]*)?|APEX_[A-Za-z0-9_$#]*|CTX_[A-Za-z0-9_$#]*"
# A procedure called as a statement: at the start of a statement, followed
# by its arguments or straight by the `;`.
STATEMENT_CALL_RE = re.compile(
    rf"(?:;|\bBEGIN\b|\bTHEN\b|\bELSE\b|\bLOOP\b)\s*((?:SYS\s*\.\s*)?({_SUPPLIED})\s*\.\s*({IDENTIFIER}))\s*(?=[(;])",
    re.IGNORECASE,
)
# What ora2pg 25.0 does convert at statement level (PLSQL.pm): DBMS_OUTPUT's
# printing (RAISE NOTICE) and ENABLE (commented out); SLEEP is GAP-123's;
# DBMS_SQL's open/parse/execute sequence is rewritten into EXECUTE as a
# whole; DBMS_STANDARD.RAISE EXCEPTION.
_CONVERTED_RE = re.compile(
    r"^(?:DBMS_OUTPUT\.(?:PUT_LINE|PUT|NEW_LINE|ENABLE)|DBMS_(?:LOCK|SESSION)\.SLEEP|DBMS_SQL\.\w+|DBMS_STANDARD\.\w+)$",
    re.IGNORECASE,
)


def statement_calls(clean: str) -> list[re.Match[str]]:
    """Every call of a supplied-package procedure as a statement in masked
    `clean`, whether ora2pg converts it or not."""
    calls = []
    for m in STATEMENT_CALL_RE.finditer(clean):
        after = m.end()
        if clean[after] == "(":
            after = skip_balanced_parens(clean, after)
        if clean[after:].lstrip().startswith(";"):
            calls.append(m)
    return calls


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
