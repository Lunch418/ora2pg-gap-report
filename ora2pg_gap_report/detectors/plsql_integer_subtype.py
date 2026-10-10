import re

from ..models import Finding
from ..number_types import declarations
from ..plsql_lex import IDENTIFIER, line_at, mask_strings_and_comments

_SUBTYPES = {"simple_integer", "natural", "naturaln", "positive", "positiven", "signtype"}
_PACKAGE_RE = re.compile(rf"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:(?:NON)?EDITIONABLE\s+)?PACKAGE\s+(?!BODY\b)(?:{IDENTIFIER}\s*\.\s*)?({IDENTIFIER})", re.IGNORECASE)


def find_plsql_integer_subtype(source: str) -> list[Finding]:
    """Detect a variable or parameter declared with one of PL/SQL's
    constrained integer subtypes: SIMPLE_INTEGER, NATURAL, NATURALN,
    POSITIVE, POSITIVEN, SIGNTYPE.

    ora2pg 25.0 maps PLS_INTEGER and BINARY_INTEGER to integer but copies
    these as they are, and PostgreSQL 16 has no such type ('type
    "simple_integer" does not exist') -- the routine does not load.
    Oracle 23ai compiles and runs it. --fix writes integer (smallint for
    SIGNTYPE); the subtype's own constraint (not null, > 0, >= 0) is not
    carried over. See docs/research/gap-136-plsql-integer-subtype.md.

    A package specification's variables are package_state's (GAP-036):
    ora2pg does not turn them into declarations at all."""
    if not re.search(r"SIMPLE_INTEGER|NATURAL|POSITIVE|SIGNTYPE", source, re.IGNORECASE):
        return []
    clean = mask_strings_and_comments(source)
    specs = {m.group(1).upper() for m in _PACKAGE_RE.finditer(clean)}
    return [
        Finding(
            detector="plsql_integer_subtype",
            severity="high",
            object_name=d.object_name,
            line=line_at(clean, d.position),
            snippet=f"{d.name} {d.type_text}" if d.name else d.type_text,
            message_id="plsql_integer_subtype",
        )
        for d in declarations(clean)
        if d.pg_type in _SUBTYPES and not (d.object_name in specs and "." not in d.object_name)
    ]
