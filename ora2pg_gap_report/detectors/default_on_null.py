import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern, statement_end

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# Oracle's actual grammar is 'DEFAULT [ON NULL] expr' -- ON NULL directly
# follows the DEFAULT keyword, *before* the expression, not after it
# (easy to get backwards; confirmed against the real syntax and against
# what ora2pg actually accepted as input, docs/research/gap-031-default-
# on-null.md). No expression can appear between DEFAULT and ON NULL, so
# there's no comma-bridging risk to guard against here, unlike a regex
# that had to search past an arbitrary expression.
_DEFAULT_ON_NULL_RE = re.compile(r"\bDEFAULT\s+ON\s+NULL\b", re.IGNORECASE)

_MESSAGE = (
    "DEFAULT ON NULL — в отличие от обычного DEFAULT, подставляется "
    "и тогда, когда столбцу явно передан NULL, а не только когда столбец "
    "пропущен в INSERT. ora2pg копирует секцию ON NULL в вывод как есть "
    "(подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-031-default-on-null.md) — PostgreSQL не "
    "поддерживает такой синтаксис у DEFAULT вообще. В отличие от "
    "большинства других находок здесь — это не тихая потеря поведения, "
    "а немедленный 'ERROR: syntax error at or near \"ON\"' уже на этапе "
    "применения самого CREATE TABLE. Нужно вручную переписать на "
    "BEFORE-триггер или GENERATED ALWAYS AS (COALESCE(...)) STORED."
)


def find_default_on_null_usage(source: str) -> list[Finding]:
    """Detect Oracle 12c+'s DEFAULT ON NULL <expr> column clause. ora2pg
    copies the ON NULL section into the generated CREATE TABLE verbatim
    -- PostgreSQL has no such DEFAULT variant at all, so this is a hard
    syntax error at DDL-apply time itself, not a later runtime surprise
    like most other gaps in this registry. See
    docs/research/gap-031-default-on-null.md.

    object_name is the table's own name (schema-level DDL) -- same
    reasoning as read_only_table.py for skipping enclosing_object_name().
    Statement scoping uses statement_end(), same as read_only_table.py."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    table_matches = list(_TABLE_RE.finditer(clean))
    for i, m in enumerate(table_matches):
        next_start = table_matches[i + 1].start() if i + 1 < len(table_matches) else None
        stmt_end = statement_end(clean, m.end(), next_start)
        statement = clean[m.end() : stmt_end]

        for default_match in _DEFAULT_ON_NULL_RE.finditer(statement):
            findings.append(
                Finding(
                    detector="default_on_null",
                    severity="high",
                    object_name=m.group(1).upper(),
                    line=line_at(clean, m.end() + default_match.start()),
                    snippet=re.sub(r"\s+", " ", default_match.group(0).strip()),
                    message=_MESSAGE,
                )
            )

    return findings
