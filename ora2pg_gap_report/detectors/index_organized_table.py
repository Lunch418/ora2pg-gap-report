import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern, statement_end

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# Excludes a double-quoted column literally named "ORGANIZATION INDEX" (a
# valid Oracle identifier) -- mask_strings_and_comments() only masks
# single-quoted string literals/comments, never double-quoted identifiers,
# so the literal text survives with its quotes intact right up against
# the words. Same guard as read_only_table.py's own READ ONLY regex.
_ORGANIZATION_INDEX_RE = re.compile(r'(?<!")\bORGANIZATION\s+INDEX\b(?!")', re.IGNORECASE)

_MESSAGE = (
    "CREATE TABLE ... ORGANIZATION INDEX — индекс-организованная таблица "
    "(IOT): данные физически хранятся в структуре первичного ключа, а не "
    "в отдельной куче со ссылками на неё из индекса. ora2pg отбрасывает "
    "секцию ORGANIZATION INDEX целиком — таблица конвертируется как "
    "обычная куча с отдельным индексом по первичному ключу (подтверждено "
    "реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-037-index-organized-table.md). Не синтаксическая "
    "ошибка и не потеря данных — ограничения целостности сохраняются, "
    "таблица работает корректно. Теряется архитектурная характеристика "
    "хранения: у PostgreSQL нет настоящих индекс-организованных таблиц "
    "(обычный PRIMARY KEY всегда создаёт отдельный индекс над отдельной "
    "кучей) — для производительность-чувствительных таблиц-кэшей, "
    "изначально спроектированных как IOT именно ради этого свойства, "
    "стоит перепроверить производительность на реальной нагрузке после "
    "миграции."
)


def find_index_organized_tables(source: str) -> list[Finding]:
    """Detect Oracle's CREATE TABLE ... ORGANIZATION INDEX. ora2pg drops
    the ORGANIZATION INDEX clause entirely, so the table converts as an
    ordinary heap table with a separate primary-key index -- correct
    with respect to integrity constraints, but not the same storage
    architecture (PostgreSQL has no true index-organized table where
    data lives physically inside the index structure). Not a
    correctness break -- a medium-severity architectural/performance
    concern for storage-sensitive lookup tables originally designed as
    an IOT for exactly that property. See
    docs/research/gap-037-index-organized-table.md.

    object_name is the table's own name (schema-level DDL) -- same
    reasoning as read_only_table.py for skipping enclosing_object_name().
    Statement scoping uses statement_end(), same as read_only_table.py."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    table_matches = list(_TABLE_RE.finditer(clean))
    for i, m in enumerate(table_matches):
        next_start = table_matches[i + 1].start() if i + 1 < len(table_matches) else None
        stmt_end = statement_end(clean, m.end(), next_start)
        statement = clean[m.end() : stmt_end]

        org_match = _ORGANIZATION_INDEX_RE.search(statement)
        if org_match is None:
            continue

        findings.append(
            Finding(
                detector="index_organized_table",
                severity="medium",
                object_name=m.group(1).upper(),
                line=line_at(clean, m.end() + org_match.start()),
                snippet="ORGANIZATION INDEX",
                message=_MESSAGE,
            )
        )

    return findings
