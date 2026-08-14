import re

from ..models import Finding
from ..plsql_lex import IDENTIFIER, enclosing_object_name, enclosing_object_name_index, line_at, mask_strings_and_comments

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

_MESSAGE = (
    "table@dblink_name — прямая ссылка на объект в удалённой базе через "
    "database link. ora2pg копирует ссылку как есть — '@dblink_name' не "
    "валидный синтаксис SQL в PostgreSQL вообще (подтверждено реальным "
    "прогоном ora2pg + PostgreSQL 16, docs/research/gap-006-database-link.md). "
    "CREATE PROCEDURE/FUNCTION проходит без ошибки (ora2pg отключает "
    "check_function_bodies в своём выводе), падает только при первом "
    "реальном вызове. Автоматической замены нет и в принципе быть не "
    "может — нужна ручная настройка postgres_fdw/dblink с реальными "
    "connection-параметрами удалённой базы."
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
    # Only for locating '@' references — mask_strings_and_comments() alone
    # doesn't blank quoted identifiers, and a literal '@' inside one
    # ('"foo@bar"') isn't a dblink reference. Same length as `clean`, so
    # positions found in it are still valid offsets into `clean` for
    # line_at()/enclosing_object_name() below.
    masked_for_search = _mask_quoted_identifiers(clean)
    findings: list[Finding] = []

    for m in _DBLINK_REF_RE.finditer(masked_for_search):
        findings.append(
            Finding(
                detector="database_link",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=m.group(0),
                message=_MESSAGE,
            )
        )

    return findings
