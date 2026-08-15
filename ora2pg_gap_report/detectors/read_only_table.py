import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern, statement_end

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# Excludes a double-quoted column literally named "READ ONLY" (a valid
# Oracle identifier) -- mask_strings_and_comments() only masks
# single-quoted string literals/comments, never double-quoted identifiers,
# so the literal text survives with its quotes intact right up against
# the words.
_READ_ONLY_RE = re.compile(r'(?<!")\bREAD\s+ONLY\b(?!")', re.IGNORECASE)

_MESSAGE = (
    "CREATE TABLE ... READ ONLY — Oracle блокирует любой INSERT/UPDATE/"
    "DELETE в такую таблицу на уровне сервера (ORA-12081), независимо от "
    "привилегий пользователя. ora2pg отбрасывает секцию READ ONLY "
    "целиком — таблица конвертируется как обычная, доступная для записи "
    "(подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-026-read-only-table.md; проверено напрямую — "
    "INSERT в сконвертированную таблицу проходит успешно там, где в "
    "Oracle он был бы гарантированно заблокирован). Не синтаксическая "
    "ошибка — CREATE TABLE выполняется без проблем, но потеряна "
    "гарантия целостности данных на уровне БД, которая могла быть "
    "единственной защитой (например, для таблицы-снапшота или "
    "исторического архива). В PostgreSQL прямого аналога нет — обычно "
    "переписывается через REVOKE INSERT/UPDATE/DELETE от всех ролей "
    "(включая владельца) или через BEFORE-триггер, отклоняющий DML."
)


def find_read_only_tables(source: str) -> list[Finding]:
    """Detect Oracle's CREATE TABLE ... READ ONLY. ora2pg drops the
    clause entirely, so the table becomes an ordinary writable one --
    not a syntax error, but a silent loss of a server-enforced integrity
    guarantee (Oracle would reject any DML against it with ORA-12081).
    See docs/research/gap-026-read-only-table.md.

    object_name is the table's own name (schema-level DDL) -- same
    reasoning as table_partitioning.py/external_table.py for skipping
    enclosing_object_name().

    Statement scoping uses statement_end() -- up to the next ';', or the
    start of the next CREATE TABLE if there's no ';' (DBMS_METADATA.GET_DDL's
    default output has none) -- not just "next ';' or end of file", which
    would otherwise misattribute a later table's own READ ONLY clause to
    an earlier, unterminated one. The reported line is the actual READ
    ONLY token's line, not the statement's opening CREATE TABLE line --
    real tables are often multi-line, and pointing at the wrong line
    sends the reader to the wrong place in the file."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    table_matches = list(_TABLE_RE.finditer(clean))
    for i, m in enumerate(table_matches):
        next_start = table_matches[i + 1].start() if i + 1 < len(table_matches) else None
        stmt_end = statement_end(clean, m.end(), next_start)
        statement = clean[m.end() : stmt_end]

        read_only_match = _READ_ONLY_RE.search(statement)
        if read_only_match is None:
            continue

        findings.append(
            Finding(
                detector="read_only_table",
                severity="high",
                object_name=m.group(1).upper(),
                line=line_at(clean, m.end() + read_only_match.start()),
                snippet="READ ONLY",
                message=_MESSAGE,
            )
        )

    return findings
