import re

from ..models import Finding
from ..mssql_lex import IDENTIFIER, mask_strings_and_comments, normalize_name
from ..plsql_lex import line_at

_NAME = rf'(?:\[[^\]]*\]|"[^"]*"|{IDENTIFIER})'
_ROUTINE_RE = re.compile(
    rf"\bCREATE\s+(?:OR\s+(?:ALTER|REPLACE)\s+)?(?:PROCEDURE|PROC|FUNCTION|TRIGGER)\s+(?:{_NAME}\s*\.\s*)*({_NAME})",
    re.IGNORECASE,
)
_NEXT_CREATE_RE = re.compile(r"\bCREATE\s+", re.IGNORECASE)
_GO_LINE_RE = re.compile(r"^[ \t]*GO(?:[ \t]+\d+)?[ \t]*;?[ \t\r]*$", re.IGNORECASE | re.MULTILINE)


def find_mssql_go_separator(source: str) -> list[Finding]:
    """Detect a routine (procedure, function, trigger) followed by the GO
    batch separator, the way SSMS scripts every one.

    ora2pg 25.0 (-M) reads a routine up to the next CREATE, so the GO goes
    into the PL/pgSQL body: `END GO END;`, and PostgreSQL 16 rejects the
    routine ('end label "go" specified for unlabeled block', or 'syntax
    error at or near "GO"' after `END;`). --prepare removes the GO lines
    and ends the closing END with `;`, a form ora2pg converts correctly.
    See docs/research/gap-126-mssql-go-separator.md.

    Reported at the GO, once per routine."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []
    for routine in _ROUTINE_RE.finditer(clean):
        nxt = _NEXT_CREATE_RE.search(clean, routine.end())
        end = nxt.start() if nxt else len(clean)
        go = _GO_LINE_RE.search(clean, routine.end(), end)
        if go is None:
            continue
        name = normalize_name(routine.group(1))
        findings.append(
            Finding(
                detector="mssql_go_separator",
                severity="high",
                object_name=name,
                line=line_at(clean, go.start() + len(go.group(0)) - len(go.group(0).lstrip())),
                snippet="GO",
                message_id="mssql_go_separator",
            )
        )
    return findings
