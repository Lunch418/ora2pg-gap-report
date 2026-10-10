from ..models import Finding
from ..number_types import declarations
from ..plsql_lex import line_at, mask_strings_and_comments


def find_number_without_precision(source: str) -> list[Finding]:
    """Detect NUMBER declared without a precision -- a column, a variable,
    a parameter, a return type: `price NUMBER`, `v NUMBER := 2.5`,
    `RETURN NUMBER`.

    Oracle's NUMBER with no precision holds any decimal value. ora2pg
    25.0, with the ora2pg.conf it ships (PG_INTEGER_TYPE 1, DEFAULT_NUMERIC
    bigint), makes every one of them bigint. Nothing fails: 9.99 stored
    in the column becomes 10, `v NUMBER := 2.5; RETURN v * 2` returns 6
    instead of 5, `p / 4` with p = 10 returns 2 instead of 2.5 -- checked
    on a live Oracle 23ai and PostgreSQL 16, see
    docs/research/gap-130-number-without-precision.md.

    Reported once per file, at the first such declaration: the cause is
    one setting, and the fix is one line in ora2pg.conf (DEFAULT_NUMERIC
    numeric) and converting again -- not a change per column."""
    clean = mask_strings_and_comments(source)
    for d in declarations(clean):
        if d.type_text.upper() == "NUMBER":
            snippet = f"{d.name} NUMBER" if d.name else "RETURN NUMBER"
            return [
                Finding(
                    detector="number_without_precision",
                    severity="high",
                    object_name=d.object_name,
                    line=line_at(clean, d.position),
                    snippet=snippet,
                    message_id="number_without_precision",
                )
            ]
    return []
