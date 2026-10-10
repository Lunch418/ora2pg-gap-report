from ..models import Finding
from ..number_types import declarations
from ..plsql_lex import line_at, mask_strings_and_comments


def find_char_semantics(source: str) -> list[Finding]:
    """Detect CHAR(n) or NCHAR(n) with n > 1 -- a column or a variable.

    Oracle keeps CHAR(n) blank-padded: CHAR(5) 'AB' is 'AB   ', its
    LENGTH is 5, `c || 'x'` is 'AB   x', and compared with a VARCHAR2
    'AB' it is not equal. ora2pg 25.0 makes it char(n), whose trailing
    blanks PostgreSQL 16 treats as insignificant: LENGTH 2, 'ABx', equal.
    Nothing fails; lengths, concatenations and comparisons change. See
    docs/research/gap-141-char-semantics.md.

    Reported once per file, at the first such declaration: the choice --
    varchar(n) with explicit padding, or keeping char(n) and checking its
    uses -- is made once for the schema. CHAR(1) flags are not reported:
    a single character has no trailing blanks."""
    if "CHAR" not in source.upper():
        return []
    clean = mask_strings_and_comments(source)
    for d in declarations(clean):
        if d.pg_type.startswith("char(") and d.pg_type != "char(1)":
            return [
                Finding(
                    detector="char_semantics",
                    severity="high",
                    object_name=d.object_name,
                    line=line_at(clean, d.position),
                    snippet=f"{d.name} {d.type_text}" if d.name else d.type_text,
                    message_id="char_semantics",
                )
            ]
    return []
