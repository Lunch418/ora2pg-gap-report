import re

from ..models import Finding
from ..plsql_lex import (
    IDENTIFIER,
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)

# SUBTYPE <name> IS <base type> RANGE <lo> .. <hi>. The RANGE part is
# required by the match: an unconstrained `SUBTYPE s IS PLS_INTEGER;`
# converts to a plain CREATE DOMAIN that loads correctly, and a
# `NOT NULL`-constrained one becomes a valid `CREATE DOMAIN ... NOT NULL`
# -- neither is a gap, so neither is flagged.
_SUBTYPE_RANGE_RE = re.compile(
    rf"\bSUBTYPE\s+({IDENTIFIER})\s+IS\s+[^;]*?\bRANGE\s+(-?\d+)\s*\.\.\s*(-?\d+)",
    re.IGNORECASE,
)

_MESSAGE = (
    "SUBTYPE ... RANGE lo .. hi — подтип PL/SQL с ограничением диапазона "
    "значений. ora2pg переводит объявление в CREATE DOMAIN, но оговорку "
    "RANGE переносит в него дословно: получается "
    "'CREATE DOMAIN pkg.small_int AS integer RANGE 1 .. 100' (подтверждено "
    "реальным прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-061-subtype-range.md). У CREATE DOMAIN в PostgreSQL "
    "такой оговорки нет, и DDL падает синтаксической ошибкой на слове "
    "RANGE. Идея переносится один в один, но другим синтаксисом — через "
    "проверку: CREATE DOMAIN small_int AS integer CHECK (VALUE BETWEEN 1 "
    "AND 100). Ненагруженные подтипы (SUBTYPE s IS PLS_INTEGER; и вариант "
    "с NOT NULL) ora2pg конвертирует корректно, и этот детектор их не "
    "помечает."
)


def find_subtype_ranges(source: str) -> list[Finding]:
    """Detect PL/SQL SUBTYPE declarations carrying a RANGE constraint.
    ora2pg turns them into CREATE DOMAIN but copies the RANGE clause
    verbatim, which PostgreSQL's CREATE DOMAIN does not accept, so the
    generated DDL fails to load. See
    docs/research/gap-061-subtype-range.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _SUBTYPE_RANGE_RE.finditer(visible):
        findings.append(
            Finding(
                detector="subtype_range",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=f"SUBTYPE {m.group(1).upper()} ... RANGE {m.group(2)} .. {m.group(3)}",
                message=_MESSAGE,
            )
        )

    return findings
