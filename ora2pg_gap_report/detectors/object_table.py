import re

from ..models import Finding
from ..plsql_lex import IDENTIFIER, line_at, mask_strings_and_comments, qualified_name_pattern

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# `OF <type>` immediately after the table name is what makes this an
# object table. Applied with .match() at the position right after the
# table name, so it's anchored there and an ordinary column list can't
# match: a column named `of` would appear after a '(', never directly
# after the table name. (No \A here -- \A would anchor at the start of
# the whole source string, not at .match()'s pos, and never fire.)
_OF_TYPE_RE = re.compile(
    rf"\s*(OF)\s+({IDENTIFIER}(?:\s*\.\s*{IDENTIFIER})?)",
    re.IGNORECASE,
)

_MESSAGE = (
    "CREATE TABLE ... OF <тип> — объектная таблица Oracle: каждая строка "
    "является экземпляром объектного типа, а атрибуты типа становятся "
    "столбцами таблицы. ora2pg не конвертирует конструкцию и не "
    "отбрасывает её — он разрушает структуру таблицы: ключевое слово OF "
    "попадает в вывод как ИМЯ СТОЛБЦА, а объявления ограничений "
    "(например 'person_id PRIMARY KEY') теряются целиком (подтверждено "
    "реальным прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-047-object-table.md). Самое опасное здесь в том, "
    "что при существующем в целевой базе типе загрузка проходит БЕЗ "
    "ОШИБКИ: создаётся таблица с единственным столбцом по имени 'of' и "
    "без первичного ключа. Миграция выглядит успешной, а таблица молча "
    "имеет неверную структуру. Переписывается вручную: объектная таблица "
    "разворачивается в обычную таблицу с отдельным столбцом на каждый "
    "атрибут типа плюс явные ограничения."
)


def find_object_tables(source: str) -> list[Finding]:
    """Detect Oracle's CREATE TABLE ... OF <object type> (object table).
    ora2pg emits the OF keyword as a column *name* and drops the
    constraint declarations entirely -- and when the type happens to
    exist in the target database, the mangled CREATE TABLE succeeds
    silently, leaving a structurally wrong table behind with no error at
    any point. See docs/research/gap-047-object-table.md.

    object_name is the table's own name (schema-level DDL) -- same
    reasoning as read_only_table.py for skipping enclosing_object_name()."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        of_match = _OF_TYPE_RE.match(clean, m.end())
        if of_match is None:
            continue

        findings.append(
            Finding(
                detector="object_table",
                severity="high",
                object_name=m.group(1).upper(),
                # The OF keyword's own position, not of_match.start(): the
                # match begins at the whitespace right after the table name,
                # and a comment can sit between the two (real case in
                # utPLSQL's ut_suite_cache.sql -- a 13-line licence header
                # between `create table` and `of`, masked to blanks by
                # mask_strings_and_comments). Reporting the match start
                # there would point at the CREATE TABLE line instead of the
                # construct itself.
                line=line_at(clean, of_match.start(1)),
                snippet=re.sub(r"\s+", " ", of_match.group(0).strip().upper()),
                message=_MESSAGE,
            )
        )

    return findings
