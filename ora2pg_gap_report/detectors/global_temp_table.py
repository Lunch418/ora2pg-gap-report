import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern

_GTT_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+GLOBAL\s+TEMPORARY\s+TABLE"),
    re.IGNORECASE,
)
_PRESERVE_ROWS_RE = re.compile(r"\bON\s+COMMIT\s+PRESERVE\s+ROWS\b", re.IGNORECASE)

_MESSAGE = (
    "CREATE GLOBAL TEMPORARY TABLE без ON COMMIT PRESERVE ROWS — то есть "
    "либо явный ON COMMIT DELETE ROWS, либо секция ON COMMIT вообще "
    "опущена (по умолчанию в Oracle это тоже DELETE ROWS). ora2pg "
    "конвертирует в CREATE TEMPORARY TABLE, но полностью теряет секцию "
    "ON COMMIT — не подставляет её PostgreSQL-эквивалент "
    "(подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-012-global-temp-table.md). У обычной CREATE "
    "TEMPORARY TABLE в PostgreSQL поведение по умолчанию — как раз "
    "PRESERVE ROWS, противоположное Oracle-семантике DELETE ROWS. Это не "
    "синтаксическая ошибка — код молча компилируется и выполняется, но "
    "строки, которые в Oracle должны были очищаться после каждого "
    "COMMIT, в PostgreSQL остаются до конца сессии. Нужно вручную "
    "добавить 'ON COMMIT DELETE ROWS' в определение таблицы."
)


def find_global_temp_tables_without_delete_rows(source: str) -> list[Finding]:
    """Detect Oracle GLOBAL TEMPORARY TABLE declarations that need
    Oracle's default/explicit ON COMMIT DELETE ROWS semantics but whose
    ora2pg conversion silently drops the ON COMMIT clause entirely,
    landing on PostgreSQL's opposite default (PRESERVE ROWS) -- a silent
    semantic change, not a syntax error, confirmed to actually happen at
    runtime (a row really does survive a COMMIT that should have cleared
    it). See docs/research/gap-012-global-temp-table.md.

    A table explicitly declared 'ON COMMIT PRESERVE ROWS' is not flagged
    -- that case matches PostgreSQL's own default and converts correctly
    (also confirmed empirically)."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _GTT_RE.finditer(clean):
        stmt_end = clean.find(";", m.end())
        if stmt_end == -1:
            stmt_end = len(clean)
        statement = clean[m.end() : stmt_end]

        if _PRESERVE_ROWS_RE.search(statement):
            continue

        findings.append(
            Finding(
                detector="global_temp_table",
                severity="high",
                object_name=m.group(1).upper(),
                line=line_at(clean, m.start()),
                snippet="CREATE GLOBAL TEMPORARY TABLE",
                message=_MESSAGE,
            )
        )

    return findings
