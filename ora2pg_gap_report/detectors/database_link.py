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

# 'table@dblink_name' (or view/synonym/function@dblink_name) — a direct
# reference to a remote object through a database link inside ordinary SQL.
# Distinct from `CREATE DATABASE LINK` itself (which just declares the
# link and is a schema object, not a text-level PL/SQL construct this
# project's detectors target). Oracle dblink names can be dotted
# (link.domain.com), unlike ordinary identifiers.
#
# '@' outside a masked string/comment/quoted-identifier has no other
# legitimate meaning in Oracle PL/SQL source (no bind-variable or operator
# uses it) — this pattern is unambiguous without needing to special-case
# SQL*Plus's leading-'@script.sql' run-command syntax, which doesn't
# appear inside a PACKAGE BODY/TRIGGER/routine body at all.
_DBLINK_REF_RE = re.compile(
    rf"\b({IDENTIFIER})@({IDENTIFIER}(?:\.{IDENTIFIER})*)",
    re.IGNORECASE,
)
# mask_strings_and_comments() only masks '...' string literals and
# comments, not "..." quoted identifiers — an Oracle quoted identifier can
# legally contain almost any character, including a literal '@'
# ('"foo@bar"' is a valid, if unusual, table name), which would otherwise
# false-positive as a database link reference.
_QUOTED_IDENTIFIER_RE = re.compile(r'"[^"]*"')


def _mask_quoted_identifiers(text: str) -> str:
    """Blank out '\"...\"' spans, preserving length and newlines (same
    contract as plsql_lex.mask_strings_and_comments) so absolute offsets
    and line numbers stay valid."""
    return _QUOTED_IDENTIFIER_RE.sub(
        lambda m: "".join("\n" if c == "\n" else " " for c in m.group(0)), text
    )


def find_database_link_references(source: str) -> list[Finding]:
    """Detect `table@dblink_name` references to remote objects through an
    Oracle database link. ora2pg has no conversion path for this at all —
    unlike most other gaps here, there's no PostgreSQL syntax this could
    even map to mechanically (postgres_fdw/dblink both require a manually
    configured foreign server, not something derivable from the reference
    alone)."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    # Search text is built from the dynamic-SQL-visible view, not `clean` --
    # a dblink reference can itself be hidden inside an EXECUTE IMMEDIATE
    # argument. Quoted identifiers still need their own masking on top: a
    # literal '@' inside one ('"foo@bar"') isn't a dblink reference. Same
    # length as `clean` either way, so positions found in it are still
    # valid offsets into `clean` for line_at()/enclosing_object_name()
    # below -- the container index itself always comes from the safe
    # `clean` view, never from dynamic SQL content, so it can't pick up a
    # fake container from something a dynamic CREATE PACKAGE/PROCEDURE
    # would create at runtime.
    masked_for_search = _mask_quoted_identifiers(mask_dynamic_sql_visible(source))
    findings: list[Finding] = []

    for m in _DBLINK_REF_RE.finditer(masked_for_search):
        findings.append(
            Finding(
                detector="database_link",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=m.group(0),
                message_id="database_link",
            )
        )

    return findings
