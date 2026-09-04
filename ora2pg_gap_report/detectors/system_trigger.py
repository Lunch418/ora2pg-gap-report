import re

from ..models import Finding
from ..plsql_lex import (
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
    qualified_name_pattern,
)

_CREATE_TRIGGER_RE = re.compile(
    qualified_name_pattern(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:EDITIONABLE\s+|NONEDITIONABLE\s+)?TRIGGER"
    ),
    re.IGNORECASE,
)
_TRIGGER_BODY_START_RE = re.compile(r"\b(DECLARE|BEGIN|CALL)\b", re.IGNORECASE)
# `ON DATABASE` / `ON SCHEMA` is what makes a trigger a *system* trigger,
# regardless of which event it fires on -- matching the scope rather than
# enumerating every event keyword (LOGON, LOGOFF, SERVERERROR, DDL,
# STARTUP, SHUTDOWN, SUSPEND, and the individual DDL events) keeps this
# complete without a keyword list that could go stale. DATABASE and SCHEMA
# are reserved enough in this position that a table by either name is not
# a realistic concern.
_SYSTEM_SCOPE_RE = re.compile(r"\bON\s+(DATABASE|SCHEMA)\b", re.IGNORECASE)


def find_system_triggers(source: str) -> list[Finding]:
    """Detect Oracle system triggers (ON DATABASE / ON SCHEMA). ora2pg
    emits them as ordinary table triggers on a table literally named
    `database`/`schema`, keeping the Oracle event keyword, so the
    generated DDL fails to parse. See
    docs/research/gap-052-system-trigger.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    findings: list[Finding] = []

    for trigger in _CREATE_TRIGGER_RE.finditer(clean):
        body = _TRIGGER_BODY_START_RE.search(visible, trigger.end())
        header_end = body.start() if body else len(visible)

        scope = _SYSTEM_SCOPE_RE.search(visible, trigger.end(), header_end)
        if scope is None:
            continue
        findings.append(
            Finding(
                detector="system_trigger",
                severity="high",
                object_name=trigger.group(1).upper(),
                line=line_at(clean, scope.start()),
                snippet=f"ON {scope.group(1).upper()}",
                message_id="system_trigger",
            )
        )

    return findings
