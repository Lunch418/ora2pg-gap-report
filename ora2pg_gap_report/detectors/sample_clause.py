import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

# Anchored on the full `SAMPLE [BLOCK] (<number>)` shape rather than the
# bare word: `sample` is an entirely ordinary identifier (a column, a
# table, a variable named `sample` is common), and only the row-sampling
# clause -- the keyword immediately followed by a parenthesised percentage
# -- is the construct that fails to convert.
_SAMPLE_RE = re.compile(
    r"\bSAMPLE\s*(?:BLOCK\s*)?\(\s*\d+(?:\.\d+)?\s*\)",
    re.IGNORECASE,
)

_MESSAGE = (
    "SAMPLE (n) / SAMPLE BLOCK (n) — выборка случайного процента строк "
    "(или блоков) таблицы прямо во FROM, Oracle-специфичный синтаксис. "
    "ora2pg копирует конструкцию в вывод как есть (подтверждено реальным "
    "прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-042-sample-clause.md). У PostgreSQL есть своя "
    "выборка, но с другим синтаксисом и другим местом в запросе — "
    "TABLESAMPLE BERNOULLI (n) / TABLESAMPLE SYSTEM (n) — поэтому "
    "скопированный как есть Oracle-вариант падает синтаксической ошибкой "
    "при загрузке. Переписывается вручную: SAMPLE (n) → TABLESAMPLE "
    "BERNOULLI (n) (построчная выборка, ближе к Oracle SAMPLE), "
    "SAMPLE BLOCK (n) → TABLESAMPLE SYSTEM (n) (поблочная, быстрее, но "
    "статистически грубее)."
)


def find_sample_clauses(source: str) -> list[Finding]:
    """Detect Oracle's SAMPLE (n) / SAMPLE BLOCK (n) row-sampling clause.
    ora2pg passes it through unchanged; PostgreSQL spells the same idea
    TABLESAMPLE with different syntax, so the generated code fails to
    load. See docs/research/gap-042-sample-clause.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _SAMPLE_RE.finditer(visible):
        findings.append(
            Finding(
                detector="sample_clause",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=" ".join(m.group(0).upper().split()),
                message=_MESSAGE,
            )
        )

    return findings
