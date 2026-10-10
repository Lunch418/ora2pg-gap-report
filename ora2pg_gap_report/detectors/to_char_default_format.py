import re

from ..lex_common import call_arguments
from ..models import Finding
from ..number_types import type_of, typed_names
from ..plsql_lex import IDENTIFIER, enclosing_object_name, enclosing_object_name_index, line_at, mask_strings_and_comments

_TO_CHAR_RE = re.compile(r"(?<![\w$#.])TO_CHAR\s*\(", re.IGNORECASE)
_NAME_RE = re.compile(rf"{IDENTIFIER}\Z")
_FRACTION_RE = re.compile(r"-?0?\.\d+\Z")  # 0.5, .5
_DATES = {"SYSDATE", "SYSTIMESTAMP", "CURRENT_DATE", "CURRENT_TIMESTAMP", "LOCALTIMESTAMP"}
_FRACTIONAL_TYPES = ("real", "double precision", "decimal(", "numeric(")


def find_to_char_default_format(source: str) -> list[Finding]:
    """Detect TO_CHAR without a format of a date or a fractional number:
    `TO_CHAR(d)` with d a DATE or TIMESTAMP variable, `TO_CHAR(SYSDATE)`,
    `TO_CHAR(v)` with v a NUMBER(p,s), `TO_CHAR(0.5)`.

    Oracle formats them its own way: a date by the session's
    NLS_DATE_FORMAT ('17-MAR-26' by default), a number without a leading
    zero ('.5'). ora2pg 25.0 turns TO_CHAR(x) into x::text, and
    PostgreSQL 16 writes '2026-03-17 00:00:00' and '0.5'. Nothing fails;
    the text differs, and with it whatever is compared, parsed or shown.
    See docs/research/gap-140-to-char-default-format.md."""
    if "TO_CHAR" not in source.upper():
        return []
    clean = mask_strings_and_comments(source)
    names = None
    index = None
    findings: list[Finding] = []
    for m in _TO_CHAR_RE.finditer(clean):
        args = call_arguments(clean, m.end() - 1)
        if len(args) != 1:
            continue
        arg = args[0].strip()
        if index is None:
            index = enclosing_object_name_index(clean)
            names = typed_names(clean)
        obj = enclosing_object_name(index, m.start())
        if arg.upper() in _DATES:
            what = arg
        elif _FRACTION_RE.match(arg):
            what = arg
        elif _NAME_RE.match(arg):
            pg_type = type_of(names or {}, obj, arg, m.start())
            if pg_type is None or not (pg_type.startswith("timestamp") or pg_type.startswith(_FRACTIONAL_TYPES)):
                continue
            what = arg
        else:
            continue
        findings.append(
            Finding(
                detector="to_char_default_format",
                severity="high",
                object_name=obj,
                line=line_at(clean, m.start()),
                snippet=f"TO_CHAR({what})",
                message_id="to_char_default_format",
            )
        )
    return findings
