import re

from ..models import Finding
from ..plsql_lex import (
    line_at,
    mask_strings_and_comments,
    qualified_name_pattern,
    statement_end,
)

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# PERIOD FOR <name> [(<start>, <end>)] -- the period name is required, the
# explicit column pair is optional (Oracle generates hidden columns when
# it's omitted). Requiring the name after FOR keeps an ordinary column
# named `period` out of the match.
_PERIOD_FOR_RE = re.compile(r"\bPERIOD\s+FOR\s+[A-Za-z_][A-Za-z0-9_$#]*", re.IGNORECASE)


def find_temporal_validity(source: str) -> list[Finding]:
    """Detect Oracle's PERIOD FOR (12c temporal validity) clause in a
    CREATE TABLE. ora2pg mangles it into a truncated `period FOR`
    fragment inside the column list, so the generated CREATE TABLE
    itself fails to load. See
    docs/research/gap-045-temporal-validity.md.

    object_name is the table's own name (schema-level DDL) -- same
    reasoning as index_organized_table.py, whose statement_end() scoping
    this mirrors."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    table_matches = list(_TABLE_RE.finditer(clean))
    for i, m in enumerate(table_matches):
        next_start = table_matches[i + 1].start() if i + 1 < len(table_matches) else None
        stmt_end = statement_end(clean, m.end(), next_start)
        statement = clean[m.end() : stmt_end]

        period_match = _PERIOD_FOR_RE.search(statement)
        if period_match is None:
            continue

        findings.append(
            Finding(
                detector="temporal_validity",
                severity="high",
                object_name=m.group(1).upper(),
                line=line_at(clean, m.end() + period_match.start()),
                snippet=re.sub(r"\s+", " ", period_match.group(0).strip().upper()),
                message_id="temporal_validity",
            )
        )

    return findings
