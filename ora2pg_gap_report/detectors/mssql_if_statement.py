import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

# Any T-SQL IF: both shapes below are broken, differently, so the
# detector deliberately doesn't try to tell them apart. The negative
# lookahead excludes IF EXISTS/IF NOT EXISTS -- not the conditional this
# detector is about, but the idempotent-DDL idiom `DROP TABLE IF EXISTS
# ...` (also PROCEDURE/VIEW/INDEX), which is neither broken by ora2pg nor
# a statement at all, and without it every DROP ... IF EXISTS line in an
# ordinary idempotent SSMS script was reported as a high-severity finding.
# Trade-off: a genuine `IF EXISTS(...) BEGIN ... END` conditional (which
# ora2pg mishandles exactly like any other IF) stops being flagged too --
# there is no regex-only way to tell the two apart, and silence here is
# the safer failure mode than flooding every idempotent script with noise.
_PATTERN_RE = re.compile(r"\bIF\b(?!\s+(?:NOT\s+)?EXISTS\b)\s+", re.IGNORECASE)

_MESSAGE = (
    "IF — условный оператор T-SQL. ora2pg (-M) не доводит перевод до "
    "конца ни в одной из двух его форм, причём ломается по-разному "
    "(подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-092-mssql-if-statement.md). С блоком — IF @x < 0 "
    "BEGIN ... END — слово THEN подставляется правильно, но закрывающее "
    "END так и остаётся END вместо END IF, и разбор падает с \'syntax "
    "error at or near \"END\"\'. Без блока — IF @x < 0 <оператор>; — не "
    "подставляется и THEN, и падение другое: \'missing \"THEN\" at end "
    "of SQL expression\'. Загрузка в обоих случаях проходит чисто "
    "(check_function_bodies = false в выводе ora2pg), ошибка вылезает "
    "при первом вызове. Переписывается в полную форму PL/pgSQL: IF "
    "<условие> THEN <операторы>; END IF;"
)


def find_mssql_if_statements(source: str) -> list[Finding]:
    """Detect T-SQL IF statements. ora2pg -M mishandles both shapes:
    with a BEGIN/END block it adds THEN but never closes with END IF,
    and without a block it adds no THEN at all. Either way the routine
    loads cleanly and fails on its first call. See docs/research/
    gap-092-mssql-if-statement.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_if_statement",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="IF",
                message=_MESSAGE,
            )
        )

    return findings
