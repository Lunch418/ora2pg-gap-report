import re

from ..lex_common import call_arguments
from ..models import Finding
from ..plsql_lex import enclosing_object_name, enclosing_object_name_index, line_at, mask_strings_and_comments

_TO_CHAR_RE = re.compile(r"(?<![\w$#.])TO_CHAR\s*\(", re.IGNORECASE)
_PARENS_RE = re.compile(r"\([^()]*\)")
_OPERATOR_RE = re.compile(r"[-+*/]")


def find_to_char_operator(source: str) -> list[Finding]:
    """Detect TO_CHAR without a format of an expression written without
    spaces: `TO_CHAR(a/b)`, `TO_CHAR(a+b)`, `TO_CHAR(-a)`.

    ora2pg 25.0 rewrites a one-argument TO_CHAR as a cast to text, and
    puts the argument in parentheses only when it has a space in it:
    TO_CHAR(a / b) becomes (a / b)::text, but TO_CHAR(a/b) becomes
    a/b::text -- where the cast binds to b alone. PostgreSQL 16 then
    rejects the expression when it runs ('operator does not exist:
    bigint / text'); Oracle 23ai returns .25 for TO_CHAR(1/4). See
    docs/research/gap-139-to-char-operator.md."""
    if "TO_CHAR" not in source.upper():
        return []
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []
    index = None
    for m in _TO_CHAR_RE.finditer(clean):
        args = call_arguments(clean, m.end() - 1)
        if len(args) != 1:
            continue
        arg = args[0].strip()
        if not arg or any(ch.isspace() for ch in arg):
            continue
        top = arg
        while _PARENS_RE.search(top):
            top = _PARENS_RE.sub("", top)
        if not _OPERATOR_RE.search(top):
            continue
        if index is None:
            index = enclosing_object_name_index(clean)
        findings.append(
            Finding(
                detector="to_char_operator",
                severity="high",
                object_name=enclosing_object_name(index, m.start()),
                line=line_at(clean, m.start()),
                snippet=f"TO_CHAR({arg})",
                message_id="to_char_operator",
            )
        )
    return findings
