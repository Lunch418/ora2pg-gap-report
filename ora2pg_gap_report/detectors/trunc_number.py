import re

from ..lex_common import call_arguments, collapse_calls, skip_balanced_parens
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

_TRUNC_RE = re.compile(r"(?<![\w$#.])TRUNC\s*\(", re.IGNORECASE)
_NUMBER_LITERAL_RE = re.compile(r"-?\s*\d+(?:\.\d+)?\Z")
_NAME_RE = re.compile(rf"{IDENTIFIER}\Z")
# Functions whose result is a number whatever their arguments are.
_NUMERIC_CALL_RE = re.compile(
    r"(?:TO_NUMBER|ABS|MOD|ROUND|FLOOR|CEIL|LENGTH|INSTR|COUNT|SUM|AVG|MONTHS_BETWEEN|POWER|SQRT|EXP|LN|LOG|SIGN|DBMS_RANDOM\s*\.\s*VALUE)\s*\(",
    re.IGNORECASE,
)
_SNIPPET_LENGTH = 40


def find_trunc_number(source: str) -> list[Finding]:
    """Detect TRUNC of a number: `TRUNC(n)` with n a numeric variable or
    parameter, `TRUNC(n / 3)`, `TRUNC(ABS(n))`, `TRUNC(x, 2)`.

    Oracle's TRUNC takes a date or a number. ora2pg 25.0 rewrites every
    TRUNC as if it were a date's: TRUNC(n / 3) becomes date_trunc('day',
    n / 3), TRUNC(n, 2) becomes date_trunc(2, n). The routine loads, and
    its first call fails in PostgreSQL 16 ('function date_trunc(unknown,
    bigint) does not exist'); Oracle 23ai returns 3 for TRUNC(10 / 3).
    See docs/research/gap-134-trunc-number.md.

    Only a TRUNC ora2pg rewrites is flagged: it hides each function call
    behind a placeholder first and takes TRUNC only when no other
    parentheses are left in it -- TRUNC((n - 1) / 26) is kept as it is
    and works. Of those, only one whose argument is visibly a number: a
    numeric literal, a numeric variable or parameter, a numeric function,
    an expression with * or /, or a second argument that is a number (a
    date's is a format string). TRUNC of a column cannot be told apart."""
    if "TRUNC" not in source.upper():
        return []
    clean = mask_strings_and_comments(source)
    names = typed_names(clean)
    index = enclosing_object_name_index(clean)
    readable = mask_comments_only(source)
    findings: list[Finding] = []
    for m in _TRUNC_RE.finditer(clean):
        args = [a.strip() for a in call_arguments(clean, m.end() - 1)]
        if not args or len(args) > 2 or not args[0]:
            continue
        inside = collapse_calls(clean[m.end() : skip_balanced_parens(clean, m.end() - 1) - 1])
        if "(" in inside or ")" in inside:
            continue  # ora2pg leaves it alone
        obj = enclosing_object_name(index, m.start())
        first = args[0]
        numeric = (
            (len(args) == 2 and bool(_NUMBER_LITERAL_RE.match(args[1])))
            or bool(_NUMBER_LITERAL_RE.match(first))
            or (bool(_NAME_RE.match(first)) and is_numeric(type_of(names, obj, first, m.start())))
            or bool(_NUMERIC_CALL_RE.match(first))
            or ("/" in first or "*" in first)
        )
        if not numeric:
            continue
        shown = " ".join(call_arguments(readable, m.end() - 1)[0].split())
        if len(shown) > _SNIPPET_LENGTH:
            shown = shown[: _SNIPPET_LENGTH - 3] + "..."
        findings.append(
            Finding(
                detector="trunc_number",
                severity="high",
                object_name=obj,
                line=line_at(clean, m.start()),
                snippet=f"TRUNC({shown}{', ' + args[1] if len(args) == 2 else ''})",
                message_id="trunc_number",
            )
        )
    return findings
