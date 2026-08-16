import re

from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)
from ..models import Finding

# Matching MODEL immediately followed by PARTITION BY/DIMENSION BY/MEASURES
# (an earlier version of this regex) has two real problems on genuine
# Oracle SQL: it false-positives on Oracle's *unrelated* "partitioned outer
# join" syntax when a table alias happens to be literally named "model"
# ('FROM t model PARTITION BY (model.x) RIGHT OUTER JOIN ...'), and it
# false-negatives on MODEL's own optional 'MAIN <name>' clause ('MODEL MAIN
# my_model DIMENSION BY ...'), which doesn't have PARTITION BY/DIMENSION
# BY/MEASURES immediately after the MODEL keyword itself.
#
# MEASURES and RULES are both *mandatory* parts of every real MODEL clause
# (PARTITION BY/DIMENSION BY/MAIN are all optional) and "RULES(" in
# particular has no other meaning in Oracle SQL/PL-SQL — requiring MODEL
# to be followed by both, within a bounded window, is robust to clause-
# option ordering/presence while avoiding the partitioned-outer-join
# collision (which never has a RULES clause nearby).
_MODEL_RE = re.compile(r"\bMODEL\b", re.IGNORECASE)
_MEASURES_RE = re.compile(r"\bMEASURES\b", re.IGNORECASE)
_RULES_RE = re.compile(r"\bRULES\b", re.IGNORECASE)
# Generous but bounded: real MODEL clauses can have a sizeable DIMENSION
# BY/MEASURES column list between MODEL and RULES, but an unrelated later
# MODEL/RULES pairing shouldn't be allowed to match across statements.
_LOOKAHEAD_WINDOW = 2000

_MESSAGE = (
    "MODEL — spreadsheet-стиль вычислений внутри SQL (PARTITION BY / "
    "DIMENSION BY / MEASURES / RULES). ora2pg не трогает конструкцию "
    "вообще (подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-007-model-clause.md). CREATE PROCEDURE/FUNCTION "
    "проходит без ошибки (ora2pg отключает check_function_bodies в своём "
    "выводе), падает только при первом реальном вызове. В отличие от "
    "большинства других находок этого проекта, у MODEL нет прямого "
    "архитектурного эквивалента в PostgreSQL вообще — единственный путь "
    "это переписать логику вручную на оконные функции или рекурсивные "
    "CTE, а не механическая подстановка синтаксиса."
)


def find_model_clauses(source: str) -> list[Finding]:
    """Detect Oracle's MODEL clause. Unlike most other detectors here,
    there is no PostgreSQL syntax this could mechanically map to at all —
    it requires understanding the business meaning of the RULES to
    redesign the query, not a syntax substitution."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _MODEL_RE.finditer(visible):
        window = visible[m.end() : m.end() + _LOOKAHEAD_WINDOW]
        if not (_MEASURES_RE.search(window) and _RULES_RE.search(window)):
            continue
        findings.append(
            Finding(
                detector="model_clause",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="MODEL",
                message=_MESSAGE,
            )
        )

    return findings
