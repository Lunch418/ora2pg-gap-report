import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

# NLSSORT(...) and NLS_SORT are two different things with confusingly
# similar names: NLSSORT() is the function that produces a collation key
# (the one ora2pg rewrites into a COLLATE clause), NLS_SORT is a session
# parameter name that usually appears *inside* NLSSORT's second argument
# ('NLS_SORT=GERMAN'). Only the function call is matched here -- the
# parameter name lives inside a string literal, which is masked out
# before this pattern ever runs.
_NLSSORT_RE = re.compile(r"\bNLSSORT\s*\(", re.IGNORECASE)

_MESSAGE = (
    "NLSSORT(...) — задание порядка сортировки по правилам конкретного "
    "языка. ora2pg переписывает вызов в PostgreSQL-овую оговорку COLLATE, "
    "подставляя имя языка из NLS_SORT прямо как имя collation: "
    "NLSSORT(name, 'NLS_SORT=GERMAN') превращается в "
    "name COLLATE \"GERMAN\" (подтверждено реальным прогоном ora2pg 25.0 + "
    "PostgreSQL 16, docs/research/gap-049-nlssort.md). Имена сортировок у "
    "Oracle и PostgreSQL не совпадают: в PostgreSQL нет collation с именем "
    "GERMAN, и запрос падает с ошибкой "
    "'collation \"GERMAN\" for encoding \"UTF8\" does not exist'. Нужно "
    "вручную сопоставить каждое Oracle-имя с реальной локалью PostgreSQL "
    "(для немецкого — \"de-DE-x-icu\" или \"de_DE.utf8\", в зависимости от "
    "того, собран ли сервер с ICU) и при необходимости создать её через "
    "CREATE COLLATION."
)


def find_nlssort(source: str) -> list[Finding]:
    """Detect Oracle's NLSSORT() collation function. ora2pg rewrites it
    into a COLLATE clause but carries the Oracle language name straight
    across, and PostgreSQL has no collation under that name, so the
    generated query fails to run. See docs/research/gap-049-nlssort.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _NLSSORT_RE.finditer(visible):
        findings.append(
            Finding(
                detector="nlssort",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="NLSSORT(",
                message=_MESSAGE,
            )
        )

    return findings
