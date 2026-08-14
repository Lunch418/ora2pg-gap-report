import re

from ..models import Finding
from ..plsql_lex import enclosing_object_name, enclosing_object_name_index, line_at, mask_strings_and_comments

# Oracle 12c+ inline function/procedure definition inside a query's own
# WITH clause. "WITH FUNCTION"/"WITH PROCEDURE" has no other meaning in
# Oracle SQL (the ordinary CTE form is always 'WITH name AS (...)').
_WITH_FUNCTION_RE = re.compile(r"\bWITH\s+(FUNCTION|PROCEDURE)\b", re.IGNORECASE)

_MESSAGE = (
    "WITH FUNCTION/PROCEDURE — встроенное определение функции внутри "
    "собственного WITH-предложения запроса (Oracle 12c+). ora2pg не "
    "просто копирует конструкцию как есть — он полностью разваливает "
    "структуру: вложенная функция 'утекает' наружу как отдельная функция "
    "верхнего уровня пакета, а тело содержащей её процедуры обрывается "
    "буквально на 'BEGIN WITH;', теряя весь настоящий запрос "
    "(подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-010-with-function.md). Падает уже на этапе "
    "компиляции тела функции при первом вызове (синтаксическая ошибка "
    "'syntax error at end of input'), не просто на выполнении. "
    "Единственный путь — вручную вынести логику в обычную функцию/"
    "процедуру PostgreSQL."
)


def find_with_function_clauses(source: str) -> list[Finding]:
    """Detect Oracle's inline WITH FUNCTION/PROCEDURE clause. Confirmed to
    cause a genuine parser corruption in ora2pg, not just an unconverted
    pass-through -- see docs/research/gap-010-with-function.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _WITH_FUNCTION_RE.finditer(clean):
        findings.append(
            Finding(
                detector="with_function",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=re.sub(r"\s+", " ", m.group(0)),
                message=_MESSAGE,
            )
        )

    return findings
