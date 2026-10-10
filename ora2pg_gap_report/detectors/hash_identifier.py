import re

from ..models import Finding
from ..plsql_lex import enclosing_object_name, enclosing_object_name_index, line_at, mask_strings_and_comments

# A name with # in it, as Oracle allows: n#count, #_OF_PRODUCTS is not one
# (a name cannot start with #) but ora2pg copies that too.
_HASH_NAME_RE = re.compile(r"(?<![\w$#])[A-Za-z_#][\w$]*#[\w$#]*|(?<![\w$#])#[A-Za-z_][\w$#]*")


def find_hash_identifier(source: str) -> list[Finding]:
    """Detect a name with # in it: a variable, a column, an alias
    (`n#count`, `emp#`).

    Oracle allows # in unquoted names. ora2pg 25.0 copies them, and
    PostgreSQL 16 does not take # in a name ('syntax error at or near
    "#"') -- the table, view or routine does not load. Found in Oracle's
    sample schemas (`as #_OF_PRODUCTS`). Rename it, or quote it in the
    output. See docs/research/gap-147-hash-identifier.md.

    Reported once per name and object."""
    if "#" not in source:
        return []
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    seen: set[tuple[str, str]] = set()
    findings: list[Finding] = []
    for m in _HASH_NAME_RE.finditer(clean):
        obj = enclosing_object_name(index, m.start())
        key = (obj, m.group(0).upper())
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            Finding(
                detector="hash_identifier",
                severity="high",
                object_name=obj,
                line=line_at(clean, m.start()),
                snippet=m.group(0),
                message_id="hash_identifier",
            )
        )
    return findings
