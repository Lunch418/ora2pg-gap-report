import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern, statement_end

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# Requiring the '(' immediately after IDENTITY is what isolates the buggy
# case: bare 'GENERATED ALWAYS AS IDENTITY' (no explicit sequence options)
# converts correctly -- confirmed empirically -- the bug only triggers
# when Oracle's own '(START WITH ... INCREMENT BY ...)' options clause is
# present for ora2pg to (incorrectly) double-wrap in an extra pair of
# parens.
_IDENTITY_WITH_OPTIONS_RE = re.compile(
    r"\bGENERATED\s+(?:ALWAYS|BY\s+DEFAULT(?:\s+ON\s+NULL)?)\s+AS\s+IDENTITY\s*\(",
    re.IGNORECASE,
)

_MESSAGE = (
    "GENERATED ALWAYS/BY DEFAULT AS IDENTITY (...) с явными опциями "
    "последовательности (START WITH/INCREMENT BY/MAXVALUE и т.д.) — "
    "ora2pg переносит их в PostgreSQL-эквивалент, но оборачивает секцию "
    "опций в лишнюю пару скобок: 'GENERATED ALWAYS AS IDENTITY "
    "((START WITH 1 INCREMENT BY 1))' вместо корректного "
    "'GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1)' "
    "(подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-028-identity-column.md). Это не пропуск "
    "конвертации, а именно баг самой подстановки — сам CREATE TABLE "
    "падает немедленно при загрузке DDL, ещё до вызова любой функции: "
    "'ERROR: syntax error at or near \"(\"'. Отдельно проверено: "
    "GENERATED ALWAYS AS IDENTITY без явных опций (пустые скобки не "
    "нужны) конвертируется корректно — баг специфичен именно для случая "
    "с опциями. Нужно вручную убрать лишнюю внешнюю пару скобок."
)


def find_identity_columns_with_options(source: str) -> list[Finding]:
    """Detect Oracle identity columns (GENERATED ALWAYS/BY DEFAULT AS
    IDENTITY) with explicit sequence generator options. Unlike most gaps
    in this registry, this isn't a missing conversion -- ora2pg's own
    substitution logic double-wraps the options clause in an extra pair
    of parens, producing DDL that fails to load at all. Confirmed to not
    reproduce for a bare 'AS IDENTITY' with no options clause. See
    docs/research/gap-028-identity-column.md.

    object_name is the table's own name (schema-level DDL) -- same
    reasoning as table_partitioning.py/external_table.py for skipping
    enclosing_object_name().

    Statement scoping uses statement_end() -- up to the next ';', or the
    start of the next CREATE TABLE if there's no ';' (DBMS_METADATA.GET_DDL's
    default output has none) -- not just "next ';' or end of file", which
    would otherwise misattribute a later table's own identity column to
    an earlier, unterminated one."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    table_matches = list(_TABLE_RE.finditer(clean))
    for i, m in enumerate(table_matches):
        next_start = table_matches[i + 1].start() if i + 1 < len(table_matches) else None
        stmt_end = statement_end(clean, m.end(), next_start)
        statement = clean[m.end() : stmt_end]
        table_name = m.group(1).upper()

        for im in _IDENTITY_WITH_OPTIONS_RE.finditer(statement):
            findings.append(
                Finding(
                    detector="identity_column",
                    severity="high",
                    object_name=table_name,
                    line=line_at(clean, m.end() + im.start()),
                    snippet="GENERATED ... AS IDENTITY (...)",
                    message=_MESSAGE,
                )
            )

    return findings
