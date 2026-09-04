import re

from ..models import Finding
from ..plsql_lex import IDENTIFIER, line_at, mask_strings_and_comments, qualified_name_pattern, statement_end

_SYNONYM_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:PUBLIC\s+)?SYNONYM"),
    re.IGNORECASE,
)
_FOR_TARGET_RE = re.compile(
    rf'\bFOR\s+(?:"?{IDENTIFIER}"?\.)?"?({IDENTIFIER})"?',
    re.IGNORECASE,
)


def find_public_synonyms(source: str) -> list[Finding]:
    """Detect Oracle's CREATE [PUBLIC] SYNONYM. ora2pg converts it to a
    plain CREATE VIEW, but drops the target object's schema entirely --
    the FOR clause's '[schema.]object' becomes an unqualified name in
    the generated FROM. When the synonym shares its target's base name
    (the common real-world convention -- that's usually the entire point
    of a synonym), the result is a self-referencing view that fails
    outright at DDL-apply time; when the names differ, resolution
    instead silently depends on the runtime search_path rather than the
    original Oracle binding. See docs/research/gap-032-public-synonym.md.

    object_name is the synonym's own name (schema-level DDL) -- same
    reasoning as read_only_table.py for skipping enclosing_object_name().
    Statement scoping uses statement_end(), same as read_only_table.py."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    syn_matches = list(_SYNONYM_RE.finditer(clean))
    for i, m in enumerate(syn_matches):
        next_start = syn_matches[i + 1].start() if i + 1 < len(syn_matches) else None
        stmt_end = statement_end(clean, m.end(), next_start)
        statement = clean[m.end() : stmt_end]

        target_match = _FOR_TARGET_RE.search(statement)
        if target_match is None:
            continue  # not a well-formed 'FOR target' -- nothing to report

        findings.append(
            Finding(
                detector="public_synonym",
                severity="high",
                object_name=m.group(1).upper(),
                line=line_at(clean, m.end()),
                snippet=f"FOR {target_match.group(1).upper()}",
                message_id="public_synonym",
            )
        )

    return findings
