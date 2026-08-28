import re

from ..models import Finding
from ..plsql_lex import (
    IDENTIFIER,
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

_PRAGMA_EXCEPTION_INIT_RE = re.compile(
    rf"\bPRAGMA\s+EXCEPTION_INIT\s*\(\s*({IDENTIFIER})\s*,\s*(-?\d+)\s*\)",
    re.IGNORECASE,
)

_MESSAGE = (
    "PRAGMA EXCEPTION_INIT — привязка объявленного исключения к номеру "
    "ошибки Oracle, чтобы ловить её по имени в WHEN. ora2pg выбрасывает "
    "сам PRAGMA и переписывает обработчик в "
    "WHEN SQLSTATE '50001' — причём в одну и ту же константу '50001' "
    "независимо от того, какой номер ORA стоял в PRAGMA (проверено на "
    "-1 и на -60, подтверждено реальным прогоном ora2pg 25.0 + "
    "PostgreSQL 16, docs/research/gap-060-pragma-exception-init.md). "
    "Процедура создаётся без единой ошибки, а обработчик становится "
    "мёртвым кодом: PostgreSQL такой SQLSTATE не возбуждает никогда, у "
    "него свои коды (нарушение уникальности — 23505, взаимоблокировка — "
    "40P01). На практике это значит, что обработанная в Oracle ошибка "
    "после миграции молча вылетает наружу и роняет вызывающий код. "
    "Каждый номер ORA нужно вручную сопоставить с настоящим кодом "
    "PostgreSQL и заменить '50001' на него (или на именованное условие "
    "вроде unique_violation)."
)


def find_pragma_exception_init(source: str) -> list[Finding]:
    """Detect Oracle's PRAGMA EXCEPTION_INIT. ora2pg drops the pragma and
    rewrites the matching handler to a fixed placeholder SQLSTATE
    ('50001') that PostgreSQL never raises, so the handler silently stops
    firing and the error escapes at runtime. See
    docs/research/gap-060-pragma-exception-init.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PRAGMA_EXCEPTION_INIT_RE.finditer(visible):
        findings.append(
            Finding(
                detector="pragma_exception_init",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=f"PRAGMA EXCEPTION_INIT({m.group(1).upper()}, {m.group(2)})",
                message=_MESSAGE,
            )
        )

    return findings
