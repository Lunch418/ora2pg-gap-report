import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern

_CREATE_TYPE_PREFIX = r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:EDITIONABLE\s+|NONEDITIONABLE\s+)?TYPE"
# VARYING ARRAY is Oracle's documented synonym for VARRAY in this clause
# (collection_type_definition: '{VARRAY | VARYING ARRAY} (size) OF ...').
_COLLECTION_TYPE_RE = re.compile(
    qualified_name_pattern(_CREATE_TYPE_PREFIX)
    + r"\s+(?:IS|AS)\s+(?:TABLE\s+OF\b|(?:VARRAY|VARYING\s+ARRAY)\s*\(\s*\d+\s*\)\s*OF\b)",
    re.IGNORECASE,
)

_MESSAGE = (
    "CREATE TYPE ... AS/IS TABLE OF / VARRAY(n) OF — коллекционный тип "
    "Oracle (nested table или varray), в отличие от объектного типа (см. "
    "GAP-009/object_type.py) не помечается ora2pg как 'Unsupported' и не "
    "копируется в вывод вообще — строка полностью пропадает, а в логе "
    "остаётся только служебная строка уровня DEBUG "
    "('unhandled line') (подтверждено реальным прогоном ora2pg + "
    "PostgreSQL 16, docs/research/gap-021-collection-type.md). Это "
    "серьёзнее большинства других gap'ов в этом реестре: любая таблица, "
    "использующая такой тип в качестве типа столбца, падает сразу при "
    "загрузке DDL — 'type ... does not exist' — а не при первом вызове "
    "процедуры. У PostgreSQL нет прямого аналога коллекционных типов "
    "Oracle — обычно переписывается на встроенный тип массива "
    "(datatype[]) или на отдельную связанную таблицу."
)


def find_collection_types(source: str) -> list[Finding]:
    """Detect Oracle collection type declarations (CREATE TYPE ... AS/IS
    TABLE OF / VARRAY(n) OF). Unlike object types (object_type.py /
    GAP-009), which ora2pg at least copies through with an explicit
    'Unsupported' marker, collection types vanish from the output
    entirely with no marker at all -- only a DEBUG-level log line. Any
    table using the type as a column type then fails outright on DDL
    load, since the type was never created. See
    docs/research/gap-021-collection-type.md.

    object_name is the type's own name (declared at schema level, never
    nested inside a package/routine) -- same reasoning as object_type.py
    for skipping enclosing_object_name()."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _COLLECTION_TYPE_RE.finditer(clean):
        findings.append(
            Finding(
                detector="collection_type",
                severity="high",
                object_name=m.group(1).upper(),
                line=line_at(clean, m.start()),
                snippet="CREATE TYPE ... TABLE OF / VARRAY OF",
                message=_MESSAGE,
            )
        )

    return findings
