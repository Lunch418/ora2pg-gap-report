import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern

_MVIEW_LOG_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+MATERIALIZED\s+VIEW\s+LOG\s+ON"),
    re.IGNORECASE,
)

_MESSAGE = (
    "CREATE MATERIALIZED VIEW LOG ON ... — журнал изменений таблицы, "
    "нужный для FAST REFRESH материализованных представлений, "
    "построенных на ней. ora2pg не конвертирует эту конструкцию вообще "
    "— она полностью пропадает из вывода, без единого предупреждения "
    "(подтверждено реальным прогоном ora2pg, "
    "docs/research/gap-027-materialized-view-log.md). В логе есть только "
    "служебная строка уровня DEBUG ('unhandled line'), не "
    "предупреждение — легко пропустить при реальной миграции. Если на "
    "этой таблице где-то построено материализованное представление с "
    "REFRESH FAST, оно перестанет работать в режиме быстрого обновления "
    "(FAST), поскольку в PostgreSQL у материализованных представлений "
    "нет инкрементального REFRESH FAST вообще — только полный REFRESH "
    "(`REFRESH MATERIALIZED VIEW`), что делает саму журнальную таблицу "
    "ненужной, но означает архитектурно другой подход к обновлению "
    "данных."
)


def find_materialized_view_logs(source: str) -> list[Finding]:
    """Detect Oracle's CREATE MATERIALIZED VIEW LOG ON <table>. ora2pg has
    no conversion path for these at all -- see
    docs/research/gap-027-materialized-view-log.md.

    object_name is the target table's name (schema-level DDL) -- same
    reasoning as table_partitioning.py/external_table.py for skipping
    enclosing_object_name()."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _MVIEW_LOG_RE.finditer(clean):
        findings.append(
            Finding(
                detector="materialized_view_log",
                severity="high",
                object_name=m.group(1).upper(),
                line=line_at(clean, m.start()),
                snippet="CREATE MATERIALIZED VIEW LOG",
                message=_MESSAGE,
            )
        )

    return findings
