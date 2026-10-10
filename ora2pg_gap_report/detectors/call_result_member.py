import re

from ..models import Finding
from ..number_types import typed_names
from .param_default_spacing import parameter_lists
from ..plsql_lex import enclosing_object_name, enclosing_object_name_index, line_at, mask_comments_only, mask_strings_and_comments

# ora2pg's own rule (PLSQL.pm): name(args).field -> name[args].field, for a
# collection element's field. Applied to a call, it breaks it.
_CALL_MEMBER_RE = re.compile(r"\b([A-Za-z_][\w$#]*)\(([^()]+)\)(\.[A-Za-z_][\w$#]*)")
_NOT_CALLS = {"TABLE", "CAST", "TREAT", "VALUE", "DEREF"}
# A declared variable: `name type :=`, `name type;`, `name type DEFAULT`.
_DECLARED_RE = re.compile(r"(?<![\w$#.])([A-Za-z_][\w$#]*)\s+[A-Za-z_][\w$#.%]*\s*(?::=|;|DEFAULT\b)", re.IGNORECASE)
# A parameter's name: first word of each item in a parameter list.
_PARAM_NAME_RE = re.compile(r"(?:^|(?<=[(,]))\s*([A-Za-z_][\w$#]*)\s+(?!,)")


def find_call_result_member(source: str) -> list[Finding]:
    """Detect a member taken from a call's result: `p_xml.extract('/a').
    getstringval()`, `get_rec(1).name`.

    ora2pg 25.0 rewrites `name(args).field` into `name[args].field` --
    meant for a collection element's field, `t(i).name` -- and does it for
    a call as well: `p_xml.extract['/a'].getstringval()`, which PostgreSQL
    16 does not parse ('syntax error at or near "("') -- the routine does
    not load. Oracle 23ai returns the text. Found in the Alexandria PL/SQL
    library (XMLTYPE extract(...).getstringval()). See
    docs/research/gap-148-call-result-member.md.

    A name declared as a variable or parameter -- a collection -- is left
    alone: that is what the rule is for."""
    if ")." not in source:
        return []
    clean = mask_strings_and_comments(source)
    readable = mask_comments_only(source)
    declared = {name for names in typed_names(clean).values() for name in names}
    declared |= {m.group(1).upper() for m in _DECLARED_RE.finditer(clean)}
    # Every routine's parameters too: p_params IN tab_param is a collection.
    for start, end in parameter_lists(clean):
        declared |= {m.group(1).upper() for m in _PARAM_NAME_RE.finditer(clean, start, end)}
    index = None
    findings: list[Finding] = []
    for m in _CALL_MEMBER_RE.finditer(clean):
        name = m.group(1).upper()
        if name in declared or name in _NOT_CALLS:
            continue
        if index is None:
            index = enclosing_object_name_index(clean)
        findings.append(
            Finding(
                detector="call_result_member",
                severity="high",
                object_name=enclosing_object_name(index, m.start()),
                line=line_at(clean, m.start()),
                snippet=" ".join(readable[m.start() : m.end()].split())[:60],
                message_id="call_result_member",
            )
        )
    return findings
