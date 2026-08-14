import re

from ..models import Finding
from ..plsql_lex import enclosing_object_name, enclosing_object_name_index, line_at, mask_strings_and_comments

# PIVOT/UNPIVOT always take a parenthesized spec ('PIVOT (aggregate FOR
# column IN (...))'), optionally preceded by their own modifier keywords
# ('PIVOT XML (...)' for a dynamic/unknown IN-list; 'UNPIVOT INCLUDE
# NULLS (...)'/'UNPIVOT EXCLUDE NULLS (...)') -- requiring the eventual
# '(' (not immediately, to allow those modifiers) rules out a bare
# "pivot"/"unpivot" used as an ordinary identifier not followed by a
# call/subclause at all.
_PIVOT_RE = re.compile(
    r"\b(PIVOT|UNPIVOT)\b\s*(?:XML\s+|(?:INCLUDE|EXCLUDE)\s+NULLS\s+)?\(",
    re.IGNORECASE,
)

_MESSAGE = (
    "PIVOT/UNPIVOT — поворот строк в столбцы (и обратно) прямо в SQL. "
    "ora2pg копирует конструкцию как есть (подтверждено реальным прогоном "
    "ora2pg + PostgreSQL 16, docs/research/gap-008-pivot-unpivot.md) — в "
    "PostgreSQL нет встроенного PIVOT/UNPIVOT вообще. CREATE "
    "PROCEDURE/FUNCTION проходит без ошибки (ora2pg отключает "
    "check_function_bodies в своём выводе), падает только при первом "
    "реальном вызове. Переписывается вручную на условную агрегацию "
    "(FILTER/CASE WHEN) или расширение tablefunc (crosstab())."
)


def find_pivot_clauses(source: str) -> list[Finding]:
    """Detect Oracle's PIVOT/UNPIVOT clause. No PostgreSQL syntax
    equivalent exists — confirmed unconverted by ora2pg and invalid
    PostgreSQL SQL (see docs/research/gap-008-pivot-unpivot.md)."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PIVOT_RE.finditer(clean):
        findings.append(
            Finding(
                detector="pivot_clause",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=m.group(1).upper(),
                message=_MESSAGE,
            )
        )

    return findings
