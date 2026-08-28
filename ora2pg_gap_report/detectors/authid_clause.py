import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

_AUTHID_RE = re.compile(r"\bAUTHID\s+(CURRENT_USER|DEFINER)\b", re.IGNORECASE)

_MESSAGE = (
    "AUTHID CURRENT_USER / AUTHID DEFINER — оговорка прав выполнения у "
    "процедуры, функции или пакета. Из всех gap'ов этого реестра последствие "
    "здесь самое неприятное: ora2pg не конвертирует объект с такой "
    "оговоркой, а молча выбрасывает его целиком — в выводе остаётся только "
    "'-- Nothing found of type PROCEDURE', и даже строки уровня DEBUG в "
    "логе не появляется (подтверждено реальным прогоном ora2pg 25.0 + "
    "PostgreSQL 16 с контрольным замером: та же процедура без AUTHID "
    "конвертируется штатно, docs/research/gap-059-authid-clause.md). "
    "Ошибки не будет ни на конвертации, ни на загрузке — процедуры просто "
    "не окажется в целевой базе, и обнаружится это при первом вызове из "
    "приложения. В PostgreSQL прямые аналоги есть: AUTHID DEFINER — это "
    "SECURITY DEFINER, AUTHID CURRENT_USER — это SECURITY INVOKER "
    "(поведение по умолчанию), так что оговорку нужно убрать из исходника "
    "перед конвертацией и дописать нужный вариант в готовую функцию."
)


def find_authid_clauses(source: str) -> list[Finding]:
    """Detect Oracle's AUTHID CURRENT_USER / AUTHID DEFINER clause.
    ora2pg silently drops the entire enclosing routine rather than
    converting it -- no output, no error, not even a DEBUG log line. See
    docs/research/gap-059-authid-clause.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _AUTHID_RE.finditer(visible):
        findings.append(
            Finding(
                detector="authid_clause",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=" ".join(m.group(0).upper().split()),
                message=_MESSAGE,
            )
        )

    return findings
