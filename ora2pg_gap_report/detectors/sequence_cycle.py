import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern, statement_end

_SEQUENCE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+SEQUENCE"),
    re.IGNORECASE,
)
# 'NOCYCLE' does NOT match here: \b requires a non-word boundary, and 'O'
# immediately preceding 'CYCLE' in 'NOCYCLE' is itself a word character,
# so there's no boundary between them -- no separate negative lookbehind
# needed (same reasoning as read_only_table.py's word-boundary handling
# of a literally-named column).
_CYCLE_RE = re.compile(r"\bCYCLE\b", re.IGNORECASE)

_MESSAGE = (
    "CREATE SEQUENCE ... CYCLE — после исчерпания диапазона (MAXVALUE/"
    "MINVALUE) Oracle начинает счёт заново, а не завершается ошибкой. "
    "ora2pg отбрасывает секцию CYCLE целиком (подтверждено реальным "
    "прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-030-sequence-cycle.md) — CREATE SEQUENCE проходит "
    "без ошибок, и последовательность работает идентично оригиналу ровно "
    "до момента исчерпания диапазона: 'ERROR: nextval: reached maximum "
    "value of sequence'. Диапазон может исчерпаться месяцы спустя после "
    "миграции, в проде, а не при тестировании. Нужно добавить CYCLE "
    "вручную в CREATE SEQUENCE, если циклическое поведение действительно "
    "нужно."
)


def find_sequence_cycle_usage(source: str) -> list[Finding]:
    """Detect Oracle's CREATE SEQUENCE ... CYCLE. ora2pg drops the CYCLE
    clause entirely, so the generated sequence raises an error once its
    range is exhausted instead of wrapping around -- not a syntax error,
    a silent loss of behavior that only surfaces once the sequence's
    range is actually exhausted (potentially long after migration). See
    docs/research/gap-030-sequence-cycle.md.

    object_name is the sequence's own name (schema-level DDL) -- same
    reasoning as read_only_table.py for skipping enclosing_object_name().
    Statement scoping uses statement_end(), same as read_only_table.py."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    seq_matches = list(_SEQUENCE_RE.finditer(clean))
    for i, m in enumerate(seq_matches):
        next_start = seq_matches[i + 1].start() if i + 1 < len(seq_matches) else None
        stmt_end = statement_end(clean, m.end(), next_start)
        statement = clean[m.end() : stmt_end]

        cycle_match = _CYCLE_RE.search(statement)
        if cycle_match is None:
            continue

        findings.append(
            Finding(
                detector="sequence_cycle",
                severity="high",
                object_name=m.group(1).upper(),
                line=line_at(clean, m.end() + cycle_match.start()),
                snippet="CYCLE",
                message=_MESSAGE,
            )
        )

    return findings
