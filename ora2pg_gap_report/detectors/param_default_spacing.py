import re

from ..lex_common import skip_balanced_parens
from ..models import Finding
from ..plsql_lex import (
    IDENTIFIER,
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_comments_only,
    mask_strings_and_comments,
)

_HEADER_RE = re.compile(rf"\b(?:FUNCTION|PROCEDURE)\s+(?:{IDENTIFIER}\s*\.\s*)?{IDENTIFIER}\s*\(", re.IGNORECASE)
_TIGHT_RE = re.compile(r"\S:=|:=\S")


def parameter_lists(clean: str) -> list[tuple[int, int]]:
    """(start, end) of each routine's parameter list in masked `clean`,
    parentheses excluded."""
    spans = []
    for m in _HEADER_RE.finditer(clean):
        close = skip_balanced_parens(clean, m.end() - 1)
        spans.append((m.end(), close - 1))
    return spans


def find_param_default_spacing(source: str) -> list[Finding]:
    """Detect a parameter default written with `:=` and no space on one
    side: `a_delimiter varchar2:= chr(10)`, `a_base integer :=0`.

    ora2pg 25.0 rewrites the := as DEFAULT without adding the space:
    `a_delimiter VARCHAR2DEFAULT chr(10)`, `a_base integer DEFAULT0` -- the
    type is not even converted -- and PostgreSQL 16 does not parse the
    routine. A variable's `v NUMBER:=0` in a declaration is copied and
    loads. Found in utPLSQL (seven functions of ut_utils). --prepare puts
    the spaces in. See docs/research/gap-144-param-default-spacing.md."""
    if ":=" not in source:
        return []
    clean = mask_strings_and_comments(source)
    readable = mask_comments_only(source)
    index = None
    findings: list[Finding] = []
    for start, end in parameter_lists(clean):
        for m in _TIGHT_RE.finditer(clean, start, end):
            # The whole parameter, as written: from the comma before to the
            # comma after.
            left = max(clean.rfind(",", start, m.start()) + 1, start)
            right = clean.find(",", m.end(), end)
            param = " ".join(readable[left : right if right != -1 else end].split())
            if index is None:
                index = enclosing_object_name_index(clean)
            findings.append(
                Finding(
                    detector="param_default_spacing",
                    severity="high",
                    object_name=enclosing_object_name(index, m.start()),
                    line=line_at(clean, m.start()),
                    snippet=param[:60],
                    message_id="param_default_spacing",
                )
            )
    return findings
