import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_SIGNAL_RE = re.compile(r"\b(SIGNAL|RESIGNAL)\b", re.IGNORECASE)

_MESSAGE = (
    "SIGNAL/RESIGNAL — MySQL/MariaDB-специфичные операторы возбуждения и "
    "повторного возбуждения условия (аналог RAISE в PL/pgSQL). ora2pg "
    "(-m) копирует SIGNAL/RESIGNAL в тело процедуры/функции дословно "
    "(теряя по пути ключевое слово SET перед MESSAGE_TEXT) — "
    "подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16 (docs/"
    "research/gap-071-mysql-signal.md). Ни SIGNAL, ни RESIGNAL в "
    "PL/pgSQL не существуют вообще. CREATE PROCEDURE/FUNCTION при этом "
    "проходит без ошибок — ora2pg выставляет в своём выводе "
    "check_function_bodies = false, поэтому тело не разбирается на "
    "загрузке, — и падение происходит при первом же реальном вызове: "
    "'syntax error at or near \"SIGNAL\"' (или \"RESIGNAL\"). "
    "Переписывается на RAISE EXCEPTION ... USING ERRCODE = '<sqlstate>', "
    "MESSAGE = '<текст>'."
)


def find_mysql_signal_statements(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's SIGNAL and RESIGNAL statements. ora2pg -m
    copies them through unchanged and PL/pgSQL has no such statement at
    all, so the containing procedure/function loads cleanly (bodies are
    not checked) and then fails on its first call. See docs/research/
    gap-071-mysql-signal.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _SIGNAL_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_signal",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=m.group(1).upper(),
                message=_MESSAGE,
            )
        )

    return findings
