import re

from ..models import Finding
from ..mysql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

_HANDLER_RE = re.compile(
    r"\bDECLARE\s+(CONTINUE|EXIT|UNDO)\s+HANDLER\b",
    re.IGNORECASE,
)

_MESSAGE = (
    "DECLARE ... HANDLER — обработчик условий в хранимой процедуре "
    "MySQL/MariaDB (CONTINUE/EXIT HANDLER FOR SQLEXCEPTION, FOR NOT "
    "FOUND, для конкретного SQLSTATE). ora2pg (-m) выбрасывает "
    "объявление из вывода целиком: на его месте в сгенерированном теле "
    "остаются пустые строки, и никакого BEGIN ... EXCEPTION WHEN ... "
    "взамен не появляется (подтверждено реальным прогоном ora2pg 25.0 + "
    "PostgreSQL 16, docs/research/gap-084-mysql-declare-handler.md; "
    "проверены обе разновидности — CONTINUE HANDLER FOR NOT FOUND и "
    "EXIT HANDLER FOR SQLEXCEPTION). Ошибки нет ни на загрузке, ни при "
    "вызове: процедура просто теряет всю обработку ошибок разом, и "
    "последствия ровно противоположны исходному замыслу — то, что MySQL "
    "глушил и продолжал выполнение, теперь вылетает наружу и обрывает "
    "транзакцию вызывающего. Восстанавливается блоком BEGIN ... "
    "EXCEPTION WHEN <условие> THEN ... END вокруг нужного участка кода. "
    "Для NOT FOUND отдельного условия в PL/pgSQL нет — оно проверяется "
    "через FOUND или GET DIAGNOSTICS сразу после запроса, так что этот "
    "случай переписывается не в EXCEPTION, а в обычный IF."
)


def find_mysql_declare_handlers(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's DECLARE ... HANDLER condition handlers.
    ora2pg -m drops them entirely, emitting no PL/pgSQL EXCEPTION block
    in their place, so a routine's whole error-handling policy silently
    disappears -- errors MySQL swallowed now propagate to the caller.
    See docs/research/gap-084-mysql-declare-handler.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _HANDLER_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mysql_declare_handler",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=f"DECLARE {m.group(1).upper()} HANDLER",
                message=_MESSAGE,
            )
        )

    return findings
