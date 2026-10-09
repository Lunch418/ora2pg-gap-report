import re

from ..mssql_lex import IDENTIFIER, mask_strings_and_comments, normalize_name
from ..models import Finding
from ..plsql_lex import line_at

_NAME = rf'(?:\[[^\]]*\]|"[^"]*"|{IDENTIFIER})'
# CREATE TABLE [dbo].[Orders], CREATE OR ALTER PROCEDURE dbo.p, ... -- a
# two-part name; a three-part db.schema.name counts by its schema.
_CREATE_QUALIFIED_RE = re.compile(
    r"\bCREATE\s+(?:OR\s+ALTER\s+)?(TABLE|VIEW|PROCEDURE|PROC|FUNCTION)\s+"
    rf"(?:{_NAME}\s*\.\s*)?({_NAME})\s*\.\s*({_NAME})",
    re.IGNORECASE,
)
_CREATE_SCHEMA_RE = re.compile(rf"\bCREATE\s+SCHEMA\s+(?:IF\s+NOT\s+EXISTS\s+)?({_NAME})", re.IGNORECASE)


def find_mssql_schema_qualified_name(source: str) -> list[Finding]:
    """Detect a CREATE of a schema-qualified object: CREATE TABLE
    [dbo].[Orders], the way SSMS writes every script.

    ora2pg 25.0 (-M) keeps the schema everywhere -- CREATE TABLE
    dbo.orders, FROM dbo.Orders in a view or a procedure -- and never
    writes a CREATE SCHEMA for it, so on a fresh PostgreSQL 16 nothing of
    it loads ('schema "dbo" does not exist'). Creating the schema is the
    whole repair, and --fix writes it. See
    docs/research/gap-125-mssql-schema-qualified-name.md.

    Reported once per schema per file, at its first use; a schema the file
    creates itself is not this gap."""
    clean = mask_strings_and_comments(source)
    created = {normalize_name(m.group(1)).lower() for m in _CREATE_SCHEMA_RE.finditer(clean)}
    findings: list[Finding] = []
    seen: set[str] = set()
    for m in _CREATE_QUALIFIED_RE.finditer(clean):
        schema = normalize_name(m.group(2))
        if schema.lower() in created or schema.lower() in seen:
            continue
        seen.add(schema.lower())
        findings.append(
            Finding(
                detector="mssql_schema_qualified_name",
                severity="high",
                object_name=f"{schema}.{normalize_name(m.group(3))}",
                line=line_at(clean, m.start(2)),
                snippet=f"{m.group(2)}.{m.group(3)}",
                message_id="mssql_schema_qualified_name",
            )
        )
    return findings
