import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

_APPLY_RE = re.compile(r"\b(CROSS|OUTER)\s+APPLY\b", re.IGNORECASE)

_MESSAGE = (
    "CROSS APPLY / OUTER APPLY (Oracle 12c+) — вызов табличного подзапроса "
    "для каждой строки внешнего запроса с возможностью ссылаться на её "
    "столбцы, аналог LATERAL JOIN. ora2pg копирует конструкцию как есть, "
    "без изменений (подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-022-cross-apply.md). PostgreSQL не имеет синтаксиса "
    "APPLY вообще — падает с синтаксической ошибкой уже на этапе "
    "компиляции тела функции при первом вызове. Нужно вручную переписать "
    "на 'JOIN LATERAL (...) ON true' (CROSS APPLY) или "
    "'LEFT JOIN LATERAL (...) ON true' (OUTER APPLY)."
)


def find_apply_joins(source: str) -> list[Finding]:
    """Detect Oracle's CROSS APPLY / OUTER APPLY. ora2pg passes it through
    unchanged; PostgreSQL has no APPLY syntax at all -- the closest
    equivalent is JOIN LATERAL / LEFT JOIN LATERAL, a manual rewrite.
    See docs/research/gap-022-cross-apply.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _APPLY_RE.finditer(visible):
        findings.append(
            Finding(
                detector="cross_apply",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=f"{m.group(1).upper()} APPLY",
                message=_MESSAGE,
            )
        )

    return findings
