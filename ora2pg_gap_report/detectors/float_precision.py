from ..models import Finding
from ..number_types import declarations
from ..plsql_lex import line_at, mask_strings_and_comments
from .package_type_anchor import package_sections


def find_float_precision(source: str) -> list[Finding]:
    """Detect FLOAT(n) declared in PL/SQL: `f FLOAT(10) := n;`.

    ora2pg 25.0 maps FLOAT to double precision and keeps the precision:
    `f double precision(10) := n;`, which PostgreSQL 16 does not parse
    ('syntax error at or near "("') -- the routine does not load. A
    column FLOAT(n) is converted to plain double precision and loads.
    Oracle 23ai compiles and runs the original. --fix drops the
    precision. See docs/research/gap-135-float-precision.md.

    A package specification is skipped: ora2pg converts its routines from
    the body."""
    if "FLOAT" not in source.upper():
        return []
    clean = mask_strings_and_comments(source)
    specs = [(package.end(), end) for package, end, is_body, _ in package_sections(clean) if not is_body]
    return [
        Finding(
            detector="float_precision",
            severity="high",
            object_name=d.object_name,
            line=line_at(clean, d.position),
            snippet=f"{d.name} {d.type_text}" if d.name else d.type_text,
            message_id="float_precision",
        )
        for d in declarations(clean)
        if not d.in_table
        and d.type_text.upper().startswith("FLOAT")
        and "(" in d.type_text
        and not any(a <= d.position < b for a, b in specs)
    ]
