from ..models import Finding
from ..number_types import declarations
from ..plsql_lex import line_at, mask_strings_and_comments

_FLOATS = ("real", "double precision")


def find_number_as_float(source: str) -> list[Finding]:
    """Detect a decimal type that ora2pg turns into binary floating point:
    NUMBER(p, s) with 0 < s <= p <= 15 (p <= 6 only in PL/SQL, where it
    becomes real; a column gets decimal(p, s)), and FLOAT.

    Oracle's NUMBER(10,2) and FLOAT are decimal: 0.1 + 0.2 = 0.3. ora2pg
    25.0, with the ora2pg.conf it ships (PG_NUMERIC_TYPE 1), makes them
    real or double precision. Nothing fails, and then: `a + b = 0.3` with
    a = 0.1, b = 0.2 is true in Oracle and false in PostgreSQL 16, the
    SUM of ten amounts of 0.1 is 1 in Oracle and 0.9999999999999999 in
    PostgreSQL -- checked on a live Oracle 23ai, see
    docs/research/gap-131-number-as-float.md.

    Reported once per file, at the first such declaration: the fix is in
    ora2pg.conf (PG_NUMERIC_TYPE 0, DATA_TYPE FLOAT:numeric) and converting
    again."""
    clean = mask_strings_and_comments(source)
    for d in declarations(clean):
        if d.pg_type in _FLOATS:
            snippet = f"{d.name} {d.type_text}" if d.name else d.type_text
            return [
                Finding(
                    detector="number_as_float",
                    severity="high",
                    object_name=d.object_name,
                    line=line_at(clean, d.position),
                    snippet=snippet,
                    message_id="number_as_float",
                )
            ]
    return []
