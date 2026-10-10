import re

from ..models import Finding
from ..number_types import is_numeric, type_of, typed_names
from ..plsql_lex import (
    IDENTIFIER,
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_comments_only,
    mask_strings_and_comments,
)

# A date operand: a name, or TRUNC of a name or of SYSDATE.
_OPERAND = rf"(?:TRUNC\s*\(\s*(?:{IDENTIFIER})\s*\)|{IDENTIFIER})"
_ARITHMETIC_RE = re.compile(
    rf"(?<![\w$#.])(?P<left>{_OPERAND})\s*(?P<op>[+-])\s*(?P<right>{_OPERAND}|\d+(?:\.\d+)?(?:\s*/\s*\d+)?)(?![\w$#.(])",
    re.IGNORECASE,
)
_TRUNC_OF_RE = re.compile(rf"TRUNC\s*\(\s*({IDENTIFIER})\s*\)\Z", re.IGNORECASE)
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?(?:\s*/\s*\d+)?\Z")  # 1, 0.5, 1/24


def find_date_arithmetic(source: str) -> list[Finding]:
    """Detect arithmetic on a DATE variable or parameter: a number added or
    subtracted (`d + 1`, `TRUNC(d) - 7`, `TRUNC(SYSDATE) - 7`) or two
    dates subtracted (`d1 - d2`, `SYSDATE - d`).

    In Oracle, date + n is a date n days later and date - date is a
    number of days. ora2pg 25.0 turns DATE into timestamp and rewrites
    SYSDATE + n into an interval, but copies these: PostgreSQL 16 has no
    timestamp + integer ('operator does not exist: timestamp without time
    zone + integer'), and timestamp - timestamp is an interval, which a
    NUMBER variable rejects ('invalid input syntax for type bigint: "2
    days"'). The routine loads and fails when it runs.
    See docs/research/gap-138-date-arithmetic.md.

    Only variables and parameters declared DATE or TIMESTAMP in the same
    routine or its package are known; a column's type is not."""
    clean = mask_strings_and_comments(source)
    if not re.search(r"\bDATE\b|\bTIMESTAMP\b", clean, re.IGNORECASE):
        return []
    names = typed_names(clean)
    index = enclosing_object_name_index(clean)
    readable = mask_comments_only(source)
    findings: list[Finding] = []

    def kind(operand: str, obj: str, position: int) -> str | None:
        """'date' (DATE), 'timestamp' (TIMESTAMP), 'sysdate', 'number' or
        None for one side of the operator."""
        trunc = _TRUNC_OF_RE.match(operand)
        name = trunc.group(1) if trunc else operand
        if name.upper() == "SYSDATE":
            return "sysdate"
        if _NUMBER_RE.match(name):
            return None if trunc else "number"
        pg_type = type_of(names, obj, name, position)
        if pg_type == "timestamp(0)":
            return "date"
        if pg_type == "timestamp":
            return "timestamp"
        return "number" if is_numeric(pg_type) and not trunc else None

    for m in _ARITHMETIC_RE.finditer(clean):
        obj = enclosing_object_name(index, m.start())
        left, right, op = kind(m.group("left"), obj, m.start()), kind(m.group("right"), obj, m.start()), m.group("op")
        sysdate_left = left == "sysdate" and not m.group("left").upper().startswith("TRUNC")
        if left in ("date", "timestamp", "sysdate") and right == "number" and not sysdate_left:
            pass  # d + 1, TRUNC(SYSDATE) - 7 (SYSDATE + n itself ora2pg converts)
        elif op == "-" and left in ("date", "sysdate") and right in ("date", "sysdate") and "date" in (left, right):
            pass  # d1 - d2, SYSDATE - d: days in Oracle (TIMESTAMP - TIMESTAMP is an interval in both)
        else:
            continue
        findings.append(
            Finding(
                detector="date_arithmetic",
                severity="high",
                object_name=obj,
                line=line_at(clean, m.start()),
                snippet=" ".join(readable[m.start() : m.end()].split()),
                message_id="date_arithmetic",
            )
        )
    return findings
