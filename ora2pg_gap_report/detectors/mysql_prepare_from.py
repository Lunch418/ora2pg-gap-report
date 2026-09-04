import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

# `PREPARE <name> FROM ...`. The FROM keyword is what distinguishes
# MySQL's spelling from PostgreSQL's own PREPARE (`PREPARE name AS
# query`), which is valid and must not be flagged -- ora2pg's output can
# legitimately contain the latter.
_PREPARE_FROM_RE = re.compile(r"\bPREPARE\s+\w+\s+FROM\b", re.IGNORECASE)


def find_mysql_prepare_from(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's `PREPARE <name> FROM <string>`. PostgreSQL
    spells its own PREPARE differently (`PREPARE name AS query`, taking
    SQL text rather than a string variable), so ora2pg -m's verbatim copy
    fails on the first call with a syntax error at FROM. PL/pgSQL's
    EXECUTE is the actual equivalent. See docs/research/
    gap-078-mysql-prepare-from.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PREPARE_FROM_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_prepare_from",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="PREPARE ... FROM",
                message_id="mysql_prepare_from",
            )
        )

    return findings
