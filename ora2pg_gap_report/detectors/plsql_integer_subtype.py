import re

from ..models import Finding
from ..number_types import declarations
from ..plsql_lex import line_at, mask_strings_and_comments
from .package_type_anchor import package_sections

_SUBTYPES = {"simple_integer", "natural", "naturaln", "positive", "positiven", "signtype"}


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

    Nothing in a package specification is flagged: its variables are
    package_state's (GAP-036), and its routines are only declared there --
    ora2pg converts them from the body, where they are flagged."""
    if not re.search(r"SIMPLE_INTEGER|NATURAL|POSITIVE|SIGNTYPE", source, re.IGNORECASE):
        return []
    clean = mask_strings_and_comments(source)
    specs = [(package.end(), end) for package, end, is_body, _ in package_sections(clean) if not is_body]
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
        if d.pg_type in _SUBTYPES and not any(a <= d.position < b for a, b in specs)
    ]
