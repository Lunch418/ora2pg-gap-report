import re

from ..models import Finding
from ..mysql_lex import (
    line_at,
    mask_strings_and_comments,
    qualified_name_pattern,
    table_column_definition_list,
)

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_FULLTEXT_RE = re.compile(r"\bFULLTEXT\s+(?:KEY|INDEX)\b", re.IGNORECASE)

_MESSAGE = (
    "FULLTEXT KEY/INDEX — полнотекстовый индекс MySQL/MariaDB, "
    "объявленный прямо в списке столбцов CREATE TABLE. ora2pg (-m) не "
    "распознаёт эту конструкцию как индекс: имя индекса и список "
    "столбцов теряются, а сами слова 'FULLTEXT KEY'/'FULLTEXT INDEX' "
    "остаются в выводе на месте, где ожидалось очередное определение "
    "столбца — подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL "
    "16 (docs/research/gap-072-mysql-fulltext-index.md). CREATE TABLE "
    "падает немедленно, при загрузке схемы: 'type \"key\" does not "
    "exist' (PostgreSQL читает 'fulltext' как имя нового столбца, а "
    "'KEY'/'INDEX' — как имя несуществующего типа для него). "
    "Восстанавливается вручную: столбцы полнотекстового индекса видны в "
    "исходном FULLTEXT KEY (...), переносятся на CREATE INDEX ... USING "
    "gin (to_tsvector('...', ...)) после CREATE TABLE."
)


def find_mysql_fulltext_indexes(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's inline `FULLTEXT KEY`/`FULLTEXT INDEX`
    column-list clause. ora2pg -m doesn't recognize it as an index at
    all: the index name and column list are dropped, and the bare
    keywords are left sitting where a column definition was expected,
    which PostgreSQL then tries (and fails) to parse as one. See
    docs/research/gap-072-mysql-fulltext-index.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        span = table_column_definition_list(clean, m.end())
        if span is None:
            continue  # bare CTAS with no column-definition list at all
        open_pos, close_pos = span
        column_list = clean[open_pos + 1 : close_pos]

        for col_match in _FULLTEXT_RE.finditer(column_list):
            findings.append(
                Finding(
                    detector="mysql_fulltext_index",
                    severity="high",
                    object_name=m.group(1).upper(),
                    line=line_at(clean, open_pos + 1 + col_match.start()),
                    snippet=col_match.group(0).upper(),
                    message=_MESSAGE,
                )
            )

    return findings
