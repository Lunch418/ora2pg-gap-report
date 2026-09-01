import re

from ..models import Finding
from ..mssql_lex import (
    line_at,
    mask_strings_and_comments,
    normalize_name,
    qualified_name_pattern,
)

_PROCEDURE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+(?:OR\s+ALTER\s+)?PROC(?:EDURE)?"),
    re.IGNORECASE,
)
# The routine's own body starts at the first standalone AS after its
# name; anything between the two is the parameter list, whether or not
# it is parenthesised (T-SQL allows both).
_AS_RE = re.compile(r"\bAS\b", re.IGNORECASE)

_MESSAGE = (
    "Процедура без параметров. Само по себе это ничем не примечательно, "
    "но ora2pg (-M) генерирует для неё пустой блок объявлений — DECLARE, "
    "пустая строка и одинокая точка с запятой, — который PL/pgSQL "
    "разобрать не может (подтверждено реальным прогоном ora2pg 25.0 + "
    "PostgreSQL 16, docs/research/"
    "gap-091-mssql-parameterless-procedure.md). Проверено прямым "
    "сравнением: у процедуры с параметром блока DECLARE в выводе нет "
    "вовсе и тело начинается сразу с BEGIN, а у точно такой же "
    "процедуры без параметров появляется сломанный DECLARE. Загрузка "
    "проходит без ошибок — ora2pg выставляет в своём выводе "
    "check_function_bodies = false, поэтому тело не разбирается, — и "
    "падение происходит при первом же реальном вызове: 'syntax error at "
    "or near \";\"'. Под это попадает каждая процедура без параметров, "
    "то есть, как правило, все служебные и отчётные. Чинится удалением "
    "пустого DECLARE из готового кода (или добавлением в него реальных "
    "переменных, если они там нужны)."
)


def find_mssql_parameterless_procedures(source: str) -> list[Finding]:
    """Detect T-SQL procedures declared with no parameters. ora2pg -M
    emits an empty `DECLARE ;` block for exactly these, which PL/pgSQL
    cannot parse, so the procedure loads cleanly and fails on its first
    call. Verified by A/B against the same procedure with a parameter,
    which comes out clean. See docs/research/
    gap-091-mssql-parameterless-procedure.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _PROCEDURE_RE.finditer(clean):
        as_match = _AS_RE.search(clean, m.end())
        if as_match is None:
            continue  # no body in this file -- nothing to say about it
        header = clean[m.end() : as_match.start()]
        if "@" in header:
            continue  # has at least one parameter: converts without the empty DECLARE
        findings.append(
            Finding(
                detector="mssql_parameterless_procedure",
                severity="high",
                object_name=normalize_name(m.group(1)).upper(),
                line=line_at(clean, m.start()),
                snippet="CREATE PROCEDURE ... AS",
                message=_MESSAGE,
            )
        )

    return findings
