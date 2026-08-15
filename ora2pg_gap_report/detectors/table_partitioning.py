import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# Requiring RANGE/LIST/HASH/REFERENCE immediately after 'PARTITION BY',
# followed by '(', is what distinguishes real table partitioning from two
# unrelated, far more common uses of the same two words: Oracle's
# "partitioned outer join" ('table_alias PARTITION BY (col) RIGHT OUTER
# JOIN ...', no such keyword at all) and a window function's
# OVER (PARTITION BY col ...) clause (same -- bare column list).
_PARTITION_BY_RE = re.compile(
    r"\bPARTITION\s+BY\s+(RANGE|LIST|HASH|REFERENCE)\s*\(", re.IGNORECASE
)
# SYSTEM partitioning has no mandatory parenthesised key -- 'PARTITION BY
# SYSTEM PARTITIONS 4' is valid without one -- so it's matched separately,
# requiring either a following '(' or the PARTITIONS keyword to still rule
# out a column literally named "system" in a window function.
_PARTITION_BY_SYSTEM_RE = re.compile(
    r"\bPARTITION\s+BY\s+(SYSTEM)\s*(?:\(|PARTITIONS\b)", re.IGNORECASE
)

_MESSAGE = (
    "PARTITION BY RANGE/LIST/HASH/REFERENCE/SYSTEM — секционирование "
    "таблицы. ora2pg полностью отбрасывает секционирование при "
    "конвертации: ни PARTITION BY, ни сами секции не попадают в вывод "
    "вообще — таблица создаётся как обычная, несекционированная "
    "(подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-013-table-partitioning.md). Совсем без "
    "предупреждения — ни в выводе, ни в --estimate_cost. Для больших "
    "таблиц это не просто синтаксическая мелочь: теряется архитектурная "
    "стратегия хранения/обслуживания (partition pruning, раздельное "
    "обслуживание партиций). PostgreSQL поддерживает декларативное "
    "партиционирование, но синтаксис отличается — секции нужно "
    "пересоздать вручную (CREATE TABLE ... PARTITION OF ...)."
)


def find_dropped_table_partitioning(source: str) -> list[Finding]:
    """Detect Oracle's PARTITION BY RANGE/LIST/HASH/REFERENCE/SYSTEM on
    CREATE TABLE. ora2pg silently drops the entire partitioning strategy --
    the table still gets created (as an ordinary, unpartitioned table)
    with no error and no warning at all. See
    docs/research/gap-013-table-partitioning.md.

    The search for PARTITION BY is scoped to each CREATE TABLE statement's
    own text (up to its terminating ';'), not matched against the nearest
    preceding CREATE TABLE anywhere in the file -- that looser approach
    both misattributed unrelated constructs (e.g. a partitioned *index*,
    'CREATE INDEX ... GLOBAL PARTITION BY RANGE (col) (...)', valid and
    distinct Oracle syntax) to whatever table happened to appear earlier in
    the file, and offered no way to tell that such a construct wasn't a
    table at all.

    object_name is the table's own name (schema-level DDL, never nested
    inside a routine) -- same reasoning as object_type.py for skipping
    enclosing_object_name()."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        stmt_end = clean.find(";", m.end())
        if stmt_end == -1:
            stmt_end = len(clean)
        statement = clean[m.end() : stmt_end]
        table_name = m.group(1).upper()

        matches = list(_PARTITION_BY_RE.finditer(statement)) + list(
            _PARTITION_BY_SYSTEM_RE.finditer(statement)
        )
        matches.sort(key=lambda mm: mm.start())

        for pm in matches:
            findings.append(
                Finding(
                    detector="table_partitioning",
                    severity="high",
                    object_name=table_name,
                    line=line_at(clean, m.end() + pm.start()),
                    snippet=f"PARTITION BY {pm.group(1).upper()}",
                    message=_MESSAGE,
                )
            )

    return findings
