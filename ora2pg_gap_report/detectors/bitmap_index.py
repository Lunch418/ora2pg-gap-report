import re

from ..models import Finding
from ..plsql_lex import IDENTIFIER, line_at, mask_strings_and_comments

# CREATE [UNIQUE] BITMAP INDEX <name> -- captures the index's own name for
# attribution. BITMAP JOIN INDEX (a separate Oracle feature built on the
# same keyword) is matched too: it converts the same way and breaks the
# same way, and the alternative -- silently ignoring it -- would be the
# worse failure mode.
_BITMAP_INDEX_RE = re.compile(
    rf"\bCREATE\s+BITMAP\s+(?:JOIN\s+)?INDEX\s+({IDENTIFIER}(?:\s*\.\s*{IDENTIFIER})?)",
    re.IGNORECASE,
)

_MESSAGE = (
    "CREATE BITMAP INDEX — битовый индекс Oracle, рассчитанный на столбцы "
    "малой кардинальности (пол, статус, флаг) и на комбинирование "
    "нескольких таких индексов побитовыми операциями. ora2pg заменяет его "
    "на 'CREATE INDEX ... USING gin(...)' (подтверждено реальным прогоном "
    "ora2pg 25.0 + PostgreSQL 16, docs/research/gap-046-bitmap-index.md). "
    "Для обычного скалярного столбца это не работает: PostgreSQL падает "
    "при загрузке с 'data type ... has no default operator class for "
    "access method \"gin\"' — у gin по умолчанию нет класса операторов ни "
    "для varchar, ни для чисел, он рассчитан на составные типы (массивы, "
    "jsonb, tsvector). То есть индекс не просто станет другим по "
    "характеристикам — его создание не пройдёт вообще. У PostgreSQL нет "
    "битовых индексов как типа; на практике замена — обычный btree "
    "(планировщик умеет комбинировать несколько btree через bitmap scan "
    "самостоятельно, во время выполнения), либо gin с явным классом "
    "операторов из расширения btree_gin, если комбинирование нужно на "
    "уровне самого индекса."
)


def find_bitmap_indexes(source: str) -> list[Finding]:
    """Detect Oracle's CREATE BITMAP INDEX. ora2pg rewrites it to a GIN
    index, which PostgreSQL refuses to create on an ordinary scalar
    column -- GIN has no default operator class for varchar or numeric --
    so the generated DDL fails at load time. See
    docs/research/gap-046-bitmap-index.md.

    object_name is the index's own name: this is standalone schema-level
    DDL, not a clause inside a CREATE TABLE, so there's no enclosing
    table to attribute it to (the target table is in the ON clause, but
    the failing object is the index itself)."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _BITMAP_INDEX_RE.finditer(clean):
        findings.append(
            Finding(
                detector="bitmap_index",
                severity="high",
                object_name=re.sub(r"\s+", "", m.group(1)).upper(),
                line=line_at(clean, m.start()),
                snippet="CREATE BITMAP INDEX",
                message=_MESSAGE,
            )
        )

    return findings
