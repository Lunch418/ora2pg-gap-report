import re

from ..models import Finding
from ..mssql_lex import line_at, mask_strings_and_comments, normalize_name

# A CREATE statement whose object name (or its schema qualifier) is
# bracket-delimited. Deliberately anchored to the CREATE, not to every
# bracket in the file: SSMS brackets *every* identifier, so flagging each
# occurrence would bury a 200-line script under 200 identical findings
# when the actionable unit is "this object will not convert". The name
# is captured with its delimiters and cleaned by normalize_name().
_BRACKETED_CREATE_RE = re.compile(
    r"\bCREATE\s+(?:OR\s+ALTER\s+)?"
    r"(?:UNIQUE\s+|CLUSTERED\s+|NONCLUSTERED\s+)*"
    r"(TABLE|PROC(?:EDURE)?|FUNCTION|VIEW|TRIGGER|INDEX)\s+"
    r"(?:\[[^\]]*\]\s*\.\s*)*"  # optional bracketed db/schema qualifiers
    r"(\[[^\]]*\])",  # the object's own bracketed name
    re.IGNORECASE,
)


def find_mssql_bracket_identifiers(source: str) -> list[Finding]:
    """Detect bracket-delimited identifiers on T-SQL CREATE statements.
    ora2pg -M's file-based path never strips them -- the brackets end up
    inside the generated identifier, and inside type names -- so the DDL
    fails to load. One finding per CREATE, not per bracket. See
    docs/research/gap-087-mssql-bracket-identifier.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _BRACKETED_CREATE_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_bracket_identifier",
                severity="high",
                object_name=normalize_name(m.group(2)).upper(),
                line=line_at(clean, m.start()),
                snippet=f"CREATE {m.group(1).upper()} {m.group(2)}",
                message_id="mssql_bracket_identifier",
            )
        )

    return findings
