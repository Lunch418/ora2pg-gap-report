import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

# Anchored on the whole KEEP (DENSE_RANK ...) shape, not a bare KEEP: the
# word on its own is a legal identifier and appears in unrelated Oracle
# code (a column named `keep`, `DBMS_*.KEEP` calls). Only the aggregate's
# own syntax -- KEEP immediately followed by a paren and DENSE_RANK -- is
# the construct that doesn't survive conversion.
_KEEP_RE = re.compile(r"\bKEEP\s*\(\s*DENSE_RANK\b", re.IGNORECASE)

_MESSAGE = (
    "KEEP (DENSE_RANK FIRST/LAST ORDER BY ...) — Oracle-специфичный "
    "вариант агрегатной функции: взять значение агрегата не по всей "
    "группе, а по строке, первой (или последней) в заданном порядке "
    "внутри группы (классика — «зарплата самого раннего нанятого в "
    "отделе»). ora2pg копирует конструкцию в вывод как есть "
    "(подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-040-keep-dense-rank.md). У PostgreSQL нет "
    "KEEP-синтаксиса — падает синтаксической ошибкой при загрузке. "
    "Переписывается вручную: чаще всего через оконную функцию "
    "FIRST_VALUE/LAST_VALUE с той же ORDER BY в OVER-разделе, либо через "
    "DISTINCT ON, либо через агрегаты PostgreSQL с FILTER."
)


def find_keep_dense_rank(source: str) -> list[Finding]:
    """Detect Oracle's KEEP (DENSE_RANK FIRST|LAST ORDER BY ...)
    aggregate modifier. ora2pg passes it through unchanged and PostgreSQL
    has no KEEP syntax, so the generated code fails to load. See
    docs/research/gap-040-keep-dense-rank.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _KEEP_RE.finditer(visible):
        findings.append(
            Finding(
                detector="keep_dense_rank",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="KEEP (DENSE_RANK ...)",
                message=_MESSAGE,
            )
        )

    return findings
