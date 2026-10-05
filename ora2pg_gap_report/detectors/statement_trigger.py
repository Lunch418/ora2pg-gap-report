import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern

_CREATE_TRIGGER_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:EDITIONABLE\s+|NONEDITIONABLE\s+)?TRIGGER"),
    re.IGNORECASE,
)
# Where the header ends: the body, or a CALL body.
_HEADER_END_RE = re.compile(r"\b(?:DECLARE|BEGIN|CALL|COMPOUND)\b", re.IGNORECASE)
_DML_TIMING_RE = re.compile(
    r"\b(?:BEFORE|AFTER)\s+(?:INSERT|UPDATE|DELETE)\b",
    re.IGNORECASE,
)
_FOR_EACH_ROW_RE = re.compile(r"\bFOR\s+EACH\s+ROW\b", re.IGNORECASE)
_SCHEMA_OR_DATABASE_RE = re.compile(r"\bON\s+(?:\w+\s*\.\s*)?(?:SCHEMA|DATABASE)\b", re.IGNORECASE)


def find_statement_trigger(source: str) -> list[Finding]:
    """Detect a statement-level DML trigger: BEFORE/AFTER INSERT/UPDATE/
    DELETE without FOR EACH ROW.

    Oracle fires it once per statement, however many rows the statement
    touches. ora2pg 25.0 writes the PostgreSQL trigger with FOR EACH ROW
    regardless, so it fires once per row. Nothing fails: the trigger loads,
    and an INSERT of five rows that ran its body once in Oracle 23ai runs
    it five times in PostgreSQL 16 -- every counter, log line or summary it
    maintains is multiplied. Reproduced from a hand-written trigger and from
    DBMS_METADATA.GET_DDL. See docs/research/gap-118-statement-trigger.md.

    Not flagged: INSTEAD OF triggers (row-level by definition), compound
    triggers (GAP-004) and triggers on SCHEMA/DATABASE (GAP-052)."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []
    for trigger in _CREATE_TRIGGER_RE.finditer(clean):
        end = _HEADER_END_RE.search(clean, trigger.end())
        header = clean[trigger.end() : end.start() if end else len(clean)]
        if end is not None and end.group(0).upper() == "COMPOUND":
            continue
        timing = _DML_TIMING_RE.search(header)
        if timing is None or _FOR_EACH_ROW_RE.search(header) or _SCHEMA_OR_DATABASE_RE.search(header):
            continue
        findings.append(
            Finding(
                detector="statement_trigger",
                severity="high",
                object_name=trigger.group(1).upper(),
                line=line_at(clean, trigger.start()),
                snippet=" ".join(timing.group(0).upper().split()) + " (no FOR EACH ROW)",
                message_id="statement_trigger",
            )
        )
    return findings
