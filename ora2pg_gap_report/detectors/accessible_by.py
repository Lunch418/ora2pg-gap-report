import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

# Anchored on the clause's own opening paren: ACCESSIBLE BY is always
# followed by a parenthesised accessor list. Excludes a double-quoted
# identifier literally named "ACCESSIBLE BY" -- mask_strings_and_comments()
# never masks double-quoted identifiers, so the text survives with its
# quotes intact, same guard as index_organized_table.py uses.
_ACCESSIBLE_BY_RE = re.compile(r'(?<!")\bACCESSIBLE\s+BY\s*\(', re.IGNORECASE)

_MESSAGE = (
    "ACCESSIBLE BY (Oracle 12c+) — «белый список» вызывающих: подпрограмма "
    "объявляется доступной только перечисленным пакетам/процедурам, "
    "остальные получают ошибку компиляции при попытке её вызвать. Это "
    "средство инкапсуляции внутри схемы, работающее поверх обычных GRANT. "
    "ora2pg копирует секцию в вывод как есть, прямо в заголовок функции "
    "(подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-043-accessible-by.md). PostgreSQL такого синтаксиса "
    "не знает — CREATE PROCEDURE/FUNCTION падает синтаксической ошибкой "
    "уже при загрузке. Прямого аналога нет: ограничение «кто именно из "
    "кода может вызвать» в PostgreSQL не выражается — ближайшее по смыслу "
    "решение это вынести подпрограмму в отдельную схему и раздать права "
    "через GRANT/REVOKE, что даёт защиту на уровне ролей, а не на уровне "
    "конкретных вызывающих подпрограмм."
)


def find_accessible_by(source: str) -> list[Finding]:
    """Detect Oracle's ACCESSIBLE BY whitelist clause on a subprogram.
    ora2pg copies it verbatim into the generated CREATE FUNCTION/PROCEDURE
    header, where PostgreSQL rejects it with a syntax error at load time.
    See docs/research/gap-043-accessible-by.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _ACCESSIBLE_BY_RE.finditer(clean):
        findings.append(
            Finding(
                detector="accessible_by",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="ACCESSIBLE BY",
                message=_MESSAGE,
            )
        )

    return findings
