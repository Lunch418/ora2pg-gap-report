import re

from ..models import Finding
from ..number_types import declarations
from ..plsql_lex import IDENTIFIER, enclosing_object_name, enclosing_object_name_index, line_at, mask_strings_and_comments

_INTEGER_TYPES = ("smallint", "integer", "bigint")
# a / b where each side is a name or an integer literal (not 2.0).
_DIVISION_RE = re.compile(
    rf"(?<![\w$#.])(?P<left>{IDENTIFIER}|\d+)(?![\w$#.(])\s*/\s*(?P<right>{IDENTIFIER}|\d+)(?![\w$#.(%])",
)
_LITERAL_RE = re.compile(r"\d+\Z")
# TRUNC(a / b) is the same in both: truncating 3.5 or taking 3.
_TRUNC_BEFORE_RE = re.compile(r"\bTRUNC\s*\(\s*\Z", re.IGNORECASE)


def _visible(names: dict[str, set[str]], obj: str, name: str) -> bool:
    """Whether `name` is declared with an integer type in `obj` or in an
    object that contains it (PKG for PKG.PROC)."""
    while True:
        if name in names.get(obj, ()):
            return True
        if "." not in obj:
            return False
        obj = obj.rsplit(".", 1)[0]


def find_integer_division(source: str) -> list[Finding]:
    """Detect a division of two integers: integer literals (`7 / 2`) or
    variables and parameters declared INTEGER, PLS_INTEGER, BINARY_INTEGER,
    SMALLINT or NUMBER(p) / NUMBER(p, 0) with p <= 19 (`i / 2`, `n / m`).

    In Oracle such a division is a NUMBER: 7 / 2 is 3.5. ora2pg 25.0 makes
    those types smallint, integer or bigint and copies the division, and
    in PostgreSQL integer division truncates: 7 / 2 is 3, -7 / 2 is -3,
    ROUND(i / 2) is 3 instead of 4. Nothing fails -- checked on a live
    Oracle 23ai and PostgreSQL 16, see docs/research/gap-132-integer-division.md.

    Not flagged: NUMBER without precision (GAP-130's, gone with its fix),
    TRUNC(a / b) and literals that divide exactly (10 / 2) -- the same
    either way -- and columns, whose types the routine's text does not
    show."""
    if "/" not in source:
        return []
    clean = mask_strings_and_comments(source)
    names: dict[str, set[str]] = {}
    for d in declarations(clean):
        if d.name and not d.in_table and d.pg_type in _INTEGER_TYPES and d.type_text.upper() != "NUMBER":
            names.setdefault(d.object_name, set()).add(d.name.upper())
    index = enclosing_object_name_index(clean)
    findings: list[Finding] = []
    for m in _DIVISION_RE.finditer(clean):
        obj = enclosing_object_name(index, m.start())

        def integer(side: str) -> bool:
            operand = m.group(side)
            return bool(_LITERAL_RE.match(operand)) or _visible(names, obj, operand.upper())

        if not (integer("left") and integer("right")):
            continue
        left, right = m.group("left"), m.group("right")
        if right.isdigit() and (int(right) == 0 or (left.isdigit() and int(left) % int(right) == 0)):
            continue  # 10 / 2 is 5 in both; x / 0 fails in both
        if _TRUNC_BEFORE_RE.search(clean, max(0, m.start() - 20), m.start()):
            continue
        findings.append(
            Finding(
                detector="integer_division",
                severity="high",
                object_name=obj,
                line=line_at(clean, m.start()),
                snippet=f"{m.group('left')} / {m.group('right')}",
                message_id="integer_division",
            )
        )
    return findings
