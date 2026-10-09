import re

from ..models import Finding
from ..plsql_lex import IDENTIFIER, line_at, mask_strings_and_comments

# A schema-qualified CREATE of the objects ora2pg keeps the schema on:
# CREATE TABLE "HR"."EMP", CREATE OR REPLACE EDITIONABLE VIEW hr.v, ...
# Not PACKAGE: ora2pg turns a package into a schema of its own name and
# drops the owner. GET_DDL quotes every name; hand-written DDL may not.
_NAME = rf'(?:"[^"]+"|{IDENTIFIER})'
_CREATE_QUALIFIED_RE = re.compile(
    r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:FORCE\s+|NO\s+FORCE\s+)?(?:(?:NON)?EDITIONABLE\s+)?"
    r"(?:GLOBAL\s+TEMPORARY\s+)?(?:UNIQUE\s+|BITMAP\s+)?"
    r"(TABLE|VIEW|MATERIALIZED\s+VIEW|SEQUENCE|PROCEDURE|FUNCTION|TRIGGER|TYPE|INDEX)\s+"
    rf"({_NAME})\s*\.\s*({_NAME})",
    re.IGNORECASE,
)
_CREATE_SCHEMA_RE = re.compile(rf"\bCREATE\s+SCHEMA\s+(?:IF\s+NOT\s+EXISTS\s+)?({_NAME})", re.IGNORECASE)


def _bare(name: str) -> str:
    return name[1:-1] if name.startswith('"') else name


def find_schema_qualified_name(source: str) -> list[Finding]:
    """Detect a CREATE of a schema-qualified object: CREATE TABLE
    "HR"."EMP", the way DBMS_METADATA.GET_DDL writes every name.

    ora2pg 25.0 keeps the schema on tables, views, sequences and routines
    (CREATE TABLE hr.emp) and never writes a CREATE SCHEMA for it, so on a
    fresh PostgreSQL 16 nothing loads ('schema "hr" does not exist'). It
    also drops the schema elsewhere -- a trigger's ON gx_emp, a view's FROM
    gx_emp -- so creating the schema alone is not enough: those fail with
    'relation "gx_emp" does not exist' until the schema is on the
    search_path too. Oracle 23ai compiles and runs the original. See
    docs/research/gap-124-schema-qualified-name.md.

    Reported once per schema per file, at its first use. A schema the
    same file creates is not this gap -- ora2pg's own output creates one
    per package and qualifies the package's routines with it."""
    clean = mask_strings_and_comments(source)
    created = {_bare(m.group(1)).lower() for m in _CREATE_SCHEMA_RE.finditer(clean)}
    findings: list[Finding] = []
    seen: set[str] = set()
    for m in _CREATE_QUALIFIED_RE.finditer(clean):
        schema = _bare(m.group(2))
        if schema.lower() in created or schema.lower() in seen:
            continue
        seen.add(schema.lower())
        name = f"{schema}.{_bare(m.group(3))}".upper()
        findings.append(
            Finding(
                detector="schema_qualified_name",
                severity="high",
                object_name=name,
                line=line_at(clean, m.start(2)),
                snippet=f"{m.group(2)}.{m.group(3)}",
                message_id="schema_qualified_name",
            )
        )
    return findings
