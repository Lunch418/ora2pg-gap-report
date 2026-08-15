import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern, statement_end

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_ORGANIZATION_EXTERNAL_RE = re.compile(r"\bORGANIZATION\s+EXTERNAL\b", re.IGNORECASE)

_MESSAGE = (
    "CREATE TABLE ... ORGANIZATION EXTERNAL — внешняя таблица Oracle, "
    "читающая данные напрямую из файла (ORACLE_LOADER/ORACLE_DATAPUMP), а "
    "не хранящая их в самой БД. ora2pg отбрасывает всю секцию "
    "ORGANIZATION EXTERNAL целиком, включая TYPE/DEFAULT DIRECTORY/"
    "ACCESS PARAMETERS/LOCATION — таблица создаётся как обычная, "
    "физически хранимая, без единого предупреждения и без сигнала в "
    "--estimate_cost (подтверждено реальным прогоном ora2pg + "
    "PostgreSQL 16, docs/research/gap-018-external-table.md). Это не "
    "синтаксическая ошибка — CREATE TABLE выполняется без проблем, но "
    "результат совсем другой: источник данных (файл) исчезает бесследно, "
    "таблица остаётся пустой и никогда не подхватит содержимое файла. "
    "Ближайший эквивалент в PostgreSQL — foreign table через file_fdw "
    "(или конкретный fdw для нужного формата) — настраивается вручную."
)


def find_external_tables(source: str) -> list[Finding]:
    """Detect Oracle's CREATE TABLE ... ORGANIZATION EXTERNAL. ora2pg
    drops the entire ORGANIZATION EXTERNAL clause, converting it into an
    ordinary physically-stored table with no error, no warning, and no
    --estimate_cost signal -- the table's actual data source (an external
    file) simply disappears. See docs/research/gap-018-external-table.md.

    Search is scoped to each CREATE TABLE statement's own text -- up to
    its terminating ';', or the start of the next CREATE TABLE if there's
    no ';' (DBMS_METADATA.GET_DDL's default output has none -- see
    statement_end()'s own docstring) -- same approach as
    table_partitioning.py, so this can't be confused with any other DDL
    that happens to precede it, terminated or not."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    table_matches = list(_TABLE_RE.finditer(clean))
    for i, m in enumerate(table_matches):
        next_start = table_matches[i + 1].start() if i + 1 < len(table_matches) else None
        stmt_end = statement_end(clean, m.end(), next_start)
        statement = clean[m.end() : stmt_end]

        if not _ORGANIZATION_EXTERNAL_RE.search(statement):
            continue

        findings.append(
            Finding(
                detector="external_table",
                severity="high",
                object_name=m.group(1).upper(),
                line=line_at(clean, m.start()),
                snippet="ORGANIZATION EXTERNAL",
                message=_MESSAGE,
            )
        )

    return findings
