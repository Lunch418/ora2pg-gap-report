import re

from ..models import Finding
from ..plsql_lex import (
    IDENTIFIER,
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

_CURSOR_DECL_RE = re.compile(rf"\bCURSOR\s+({IDENTIFIER})\b", re.IGNORECASE)
# `<name>%ROWTYPE`, where <name> is captured so it can be checked against
# the cursors declared in the same source. A qualified `schema.table` or a
# bare table name is the supported form and must not be flagged, so the
# name is deliberately matched without a dot.
_ROWTYPE_RE = re.compile(rf"(?<![.\w])({IDENTIFIER})\s*%\s*ROWTYPE", re.IGNORECASE)


def find_cursor_rowtype(source: str) -> list[Finding]:
    """Detect PL/SQL `<cursor>%ROWTYPE` declarations. PL/pgSQL supports
    %ROWTYPE only against a table or view, so ora2pg's verbatim copy
    fails at first call with 'relation ... does not exist'. Only names
    that are actually declared as a CURSOR in the same source are
    flagged, so ordinary `<table>%ROWTYPE` -- which converts correctly --
    stays clean. See docs/research/gap-064-cursor-rowtype.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)

    cursor_names = {m.group(1).upper() for m in _CURSOR_DECL_RE.finditer(visible)}
    if not cursor_names:
        return []

    findings: list[Finding] = []
    for m in _ROWTYPE_RE.finditer(visible):
        name = m.group(1).upper()
        if name not in cursor_names:
            continue
        findings.append(
            Finding(
                detector="cursor_rowtype",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=f"{m.group(1).lower()}%ROWTYPE",
                message_id="cursor_rowtype",
            )
        )

    return findings
