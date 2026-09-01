import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

# '@@IDENTITY' cannot use a leading \b: '@' is not a word character, so
# there is no boundary between it and the preceding space. Matched as its
# own alternative instead.
_PATTERN_RE = re.compile(r"(?:\b(SCOPE_IDENTITY|IDENT_CURRENT)\b|(@@IDENTITY)\b)", re.IGNORECASE)

_MESSAGE = (
    "SCOPE_IDENTITY() / @@IDENTITY / IDENT_CURRENT() — способы узнать "
    "значение, выданное IDENTITY при последней вставке в SQL Server. "
    "ora2pg (-M) копирует вызов в тело процедуры дословно (подтверждено "
    "реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/"
    "gap-096-mssql-scope-identity.md). Ни такой функции, ни такой "
    "системной переменной в PostgreSQL нет, и при первом же реальном "
    "вызове процедура падает; загрузка проходит чисто, потому что "
    "ora2pg выставляет в своём выводе check_function_bodies = false. "
    "Переписывается лучше всего на INSERT ... RETURNING <столбец> INTO "
    "<переменная>: значение берётся прямо из выполненной вставки. "
    "Учтите, что сам столбец IDENTITY при этом тоже теряется "
    "(GAP-090), так что возвращать может быть уже нечего — эти два "
    "места правятся вместе."
)


def find_mssql_scope_identity(source: str) -> list[Finding]:
    """Detect SCOPE_IDENTITY()/@@IDENTITY/IDENT_CURRENT(). ora2pg -M
    copies them through unchanged and PostgreSQL has no such function or
    system variable, so the containing routine loads cleanly and fails on
    its first call. See docs/research/gap-096-mssql-scope-identity.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_scope_identity",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=(m.group(1) or m.group(2)).upper(),
                message=_MESSAGE,
            )
        )

    return findings
