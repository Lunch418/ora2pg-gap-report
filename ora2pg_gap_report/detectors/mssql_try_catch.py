import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_PATTERN_RE = re.compile(r"\bBEGIN\s+TRY\b", re.IGNORECASE)

_MESSAGE = (
    "BEGIN TRY ... END TRY BEGIN CATCH ... END CATCH — обработка ошибок "
    "в T-SQL. ora2pg (-M) копирует всю конструкцию в тело процедуры "
    "дословно, включая END TRY и END CATCH (подтверждено реальным "
    "прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/"
    "gap-094-mssql-try-catch.md). В PL/pgSQL обработка ошибок пишется "
    "иначе — BEGIN ... EXCEPTION WHEN <условие> THEN ... END, — и такого "
    "синтаксиса там нет. Загрузка проходит чисто (check_function_bodies "
    "= false в выводе ora2pg), падение — при первом реальном вызове. "
    "Переписывается на блок BEGIN ... EXCEPTION WHEN OTHERS THEN ... "
    "END, причём вызовы вида ERROR_MESSAGE() внутри CATCH заменяются на "
    "SQLERRM, а ERROR_NUMBER() — на SQLSTATE."
)


def find_mssql_try_catch(source: str) -> list[Finding]:
    """Detect T-SQL BEGIN TRY/BEGIN CATCH blocks. ora2pg -M copies the
    whole construct through unchanged; PL/pgSQL spells error handling as
    BEGIN ... EXCEPTION WHEN ... END, so the routine loads cleanly and
    fails on its first call. See docs/research/gap-094-mssql-try-catch.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_try_catch",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="BEGIN TRY",
                message=_MESSAGE,
            )
        )

    return findings
