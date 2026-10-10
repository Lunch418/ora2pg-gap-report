import re

from ..lex_common import call_arguments
from ..models import Finding
from ..number_types import type_of, typed_names
from ..plsql_lex import (
    IDENTIFIER,
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_comments_only,
    mask_strings_and_comments,
)

_ROUND_RE = re.compile(r"(?<![\w$#.])ROUND\s*\(", re.IGNORECASE)
_NAME_RE = re.compile(rf"{IDENTIFIER}\Z")
_STRING_RE = re.compile(r"'(?:[^']|'')*'\Z")
_DATES = {"SYSDATE", "SYSTIMESTAMP", "CURRENT_DATE"}


def find_round_date(source: str) -> list[Finding]:
    """Detect ROUND of a date: `ROUND(d, 'MM')` (a format, which only a
    date's ROUND takes), `ROUND(d)` with d a DATE or TIMESTAMP variable,
    `ROUND(SYSDATE)`.

    ora2pg 25.0 rewrites TRUNC(d, 'MM') into date_trunc('month', d) but
    copies ROUND, and PostgreSQL 16 has no round for a timestamp
    ('function round(timestamp without time zone, unknown) does not
    exist') -- the routine loads and fails when it runs. Oracle 23ai
    returns 2026-04-01 for ROUND(DATE '2026-03-17', 'MM'). See
    docs/research/gap-142-round-date.md."""
    if "ROUND" not in source.upper():
        return []
    clean = mask_strings_and_comments(source)
    readable = mask_comments_only(source)
    names = None
    index = None
    findings: list[Finding] = []
    for m in _ROUND_RE.finditer(clean):
        args = call_arguments(clean, m.end() - 1)
        if not args or len(args) > 2:
            continue
        if index is None:
            index = enclosing_object_name_index(clean)
            names = typed_names(clean)
        obj = enclosing_object_name(index, m.start())
        shown = call_arguments(readable, m.end() - 1)
        first = args[0].strip()
        if len(args) == 2 and _STRING_RE.match(shown[1].strip()):
            pass  # ROUND(x, 'MM')
        elif first.upper() in _DATES or (
            _NAME_RE.match(first) and (type_of(names or {}, obj, first, m.start()) or "").startswith("timestamp")
        ):
            pass  # ROUND(d)
        else:
            continue
        findings.append(
            Finding(
                detector="round_date",
                severity="high",
                object_name=obj,
                line=line_at(clean, m.start()),
                snippet="ROUND(" + ", ".join(" ".join(a.split()) for a in shown) + ")",
                message_id="round_date",
            )
        )
    return findings
