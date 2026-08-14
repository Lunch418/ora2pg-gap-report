import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern

_CREATE_TYPE_PREFIX = r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:EDITIONABLE\s+|NONEDITIONABLE\s+)?TYPE"
# Oracle treats IS and AS as interchangeable here, same as everywhere else
# in PL/SQL declarations (see plsql_lex._IS_AS_RE).
_TYPE_AS_OBJECT_RE = re.compile(
    qualified_name_pattern(_CREATE_TYPE_PREFIX) + r"\s+(?:IS|AS)\s+OBJECT\b",
    re.IGNORECASE,
)
_TYPE_BODY_RE = re.compile(
    qualified_name_pattern(_CREATE_TYPE_PREFIX + r"\s+BODY"),
    re.IGNORECASE,
)
_PATTERNS = (
    (_TYPE_AS_OBJECT_RE, "CREATE TYPE ... AS OBJECT"),
    (_TYPE_BODY_RE, "CREATE TYPE BODY"),
)

_MESSAGE = (
    "CREATE TYPE ... AS OBJECT / TYPE BODY — объектный тип Oracle "
    "(атрибуты + MEMBER-методы). ora2pg сам явно помечает это "
    "'-- Unsupported, please edit to match PostgreSQL syntax' и копирует "
    "Oracle-синтаксис как есть — но что важнее, у --estimate_cost (и, "
    "судя по коду, у SHOW_REPORT) вообще нет механизма оценки стоимости "
    "для объектов типа TYPE (подтверждено прогоном --estimate_cost -t "
    "TYPE, вернувшим ноль строк отчёта, см. "
    "docs/research/gap-009-object-type.md). Значит такие объекты не "
    "просто помечены как проблема — они полностью выпадают из любой "
    "числовой оценки трудозатрат. У PostgreSQL нет объектных типов с "
    "методами — обычно переписывается на composite type + отдельные "
    "функции, архитектурно другой подход, не механическая замена "
    "синтаксиса."
)


def find_object_types(source: str) -> list[Finding]:
    """Detect Oracle object type declarations (CREATE TYPE ... AS/IS
    OBJECT and CREATE TYPE BODY). Unlike this project's other detectors,
    the value here isn't "ora2pg silently produces broken code" -- ora2pg
    already marks these unsupported in its own output -- it's that these
    objects get zero cost estimate at all, so a schema with substantial
    OOP-style Oracle usage would show artificially low estimated effort.
    object_name is the type's own name (declared at schema level, never
    nested inside a package/routine), not resolved via
    enclosing_object_name() like the source-level detectors -- a type
    declaration is never nested inside anything else, so that shared
    attribution logic would be dead code here, not extra correctness."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for pattern, snippet in _PATTERNS:
        for m in pattern.finditer(clean):
            findings.append(
                Finding(
                    detector="object_type",
                    severity="high",
                    object_name=m.group(1).upper(),
                    line=line_at(clean, m.start()),
                    snippet=snippet,
                    message=_MESSAGE,
                )
            )

    return findings
