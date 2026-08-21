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

# A local nested-table/associative-array collection type ('TYPE t IS TABLE
# OF ...;' inside a DECLARE section), not a schema-level 'CREATE [OR
# REPLACE] TYPE ... IS TABLE OF ... AS OBJECT' (a different, separately
# handled Oracle feature for column-usable collection types) — excluded via
# _schema_level_create_type_positions below.
_LOCAL_COLLECTION_TYPE_RE = re.compile(rf"\bTYPE\s+{IDENTIFIER}\s+IS\s+TABLE\s+OF\b", re.IGNORECASE)
_BULK_COLLECT_RE = re.compile(r"\bBULK\s+COLLECT\s+INTO\b", re.IGNORECASE)
_FORALL_RE = re.compile(r"\bFORALL\b", re.IGNORECASE)

# A schema-level 'CREATE [OR REPLACE] [EDITIONABLE|NONEDITIONABLE] TYPE'
# prefix -- matched with a lookahead so m.end() lands exactly where 'TYPE'
# starts, the same offset _LOCAL_COLLECTION_TYPE_RE's own match starts at.
# \s+ between the keywords also swallows a masked comment of any length
# (e.g. 'CREATE OR REPLACE /* ... */ TYPE') -- see
# _schema_level_create_type_positions below for why this must stay a
# single forward pass rather than a per-match backward search.
_CREATE_TYPE_PREFIX_RE = re.compile(
    r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:EDITIONABLE\s+|NONEDITIONABLE\s+)?(?=TYPE\b)",
    re.IGNORECASE,
)

_TYPE_DECL_MESSAGE = (
    "TYPE ... IS TABLE OF ... — локальное объявление вложенной "
    "коллекции/ассоциативного массива. ora2pg практически не трогает эту "
    "конструкцию — синтаксис копируется как есть, а такого объявления "
    "типа не существует в PL/pgSQL (подтверждено реальным прогоном ora2pg "
    "+ PostgreSQL 16, docs/research/gap-003-bulk-collect-forall.md). "
    "CREATE PROCEDURE/FUNCTION проходит без единой ошибки (ora2pg "
    "отключает check_function_bodies в своём выводе), а при первом же "
    "реальном вызове падает прямо на этом объявлении — до того, как тело "
    "процедуры вообще начнёт выполняться. Нужно вручную переписать на "
    "массив PostgreSQL (type[]) или временную таблицу."
)
_BULK_COLLECT_MESSAGE = (
    "BULK COLLECT INTO — массовая выборка в коллекцию. ora2pg лишь "
    "добавляет ключевое слово STRICT (относящееся к обычному SELECT INTO "
    "в PL/pgSQL, а не к BULK COLLECT) и не переписывает конструкцию — "
    "результат не является корректным PL/pgSQL (подтверждено реальным "
    "прогоном, docs/research/gap-003-bulk-collect-forall.md). Обычно "
    "переписывается на 'SELECT array_agg(...) INTO ...' или цикл с "
    "накоплением в массив вручную."
)
_FORALL_MESSAGE = (
    "FORALL — массовое DML-выполнение по коллекции. В PL/pgSQL такой "
    "конструкции нет, ora2pg копирует её как есть (подтверждено реальным "
    "прогоном, docs/research/gap-003-bulk-collect-forall.md). Обычно "
    "переписывается на обычный цикл FOR ... LOOP или на DML с UNNEST() "
    "по массиву — оценка производительности отдельно, PostgreSQL это "
    "тоже умеет делать быстро, просто другим синтаксисом."
)


def _schema_level_create_type_positions(text: str) -> set[int]:
    """Every offset where a schema-level 'CREATE [OR REPLACE] TYPE ... IS
    TABLE OF' (an object type usable in table columns, a different Oracle
    feature — already handled separately, not this detector's concern)
    starts its 'TYPE' keyword — as opposed to a local 'TYPE t IS TABLE OF
    ...' inside a routine's DECLARE section, which isn't in this set.

    One forward finditer pass over the whole text (O(n) total), not a
    backward re.search(text[:match_start], ...) run once per
    _LOCAL_COLLECTION_TYPE_RE match: that used to re-copy and re-scan an
    ever-growing prefix on every single match, making the whole detector
    O(n^2) on a source file with many local TYPE declarations (profiled:
    ~3.5x wall-clock time for a 2x input, the signature of quadratic
    growth). A single pass building this set, checked with an O(1) 'in'
    per match afterwards, avoids that entirely.

    _CREATE_TYPE_PREFIX_RE's \\s+ between keywords still swallows a masked
    comment of any length between 'CREATE OR REPLACE' and 'TYPE' — the
    forward pass doesn't reintroduce the old fixed-window bug (a masked
    comment longer than the window wrongly missing the CREATE prefix)
    that a naive bounded-lookbehind fix would risk. Also allows an
    EDITIONABLE/NONEDITIONABLE modifier between 'OR REPLACE' and 'TYPE'
    (Oracle 12c+) — missing it caused a real schema-level collection type
    declared with this modifier to be double-reported: once correctly by
    collection_type.py, and once incorrectly by this detector, which is
    only meant to catch the local 'TYPE t IS TABLE OF ...' form nested
    inside a routine's DECLARE section."""
    return {m.end() for m in _CREATE_TYPE_PREFIX_RE.finditer(text)}


def find_bulk_collect_usage(source: str) -> list[Finding]:
    """Detect Oracle's bulk-operations idiom: a local nested-table/
    associative-array TYPE declaration, BULK COLLECT INTO, and FORALL.
    ora2pg leaves all three essentially unconverted (see
    docs/research/gap-003-bulk-collect-forall.md) — far more common in
    real-world Oracle PL/SQL than any of this project's other detector
    targets, and unlike them, fails immediately (often on the type
    declaration itself, before the routine body runs anything).

    One finding per occurrence, same granularity as dbms_utl_calls.py —
    a routine using all three within the same block gets three findings,
    not one deduplicated one; each is independently informative about
    where the rewrite has to happen.
    """
    clean = mask_strings_and_comments(source)
    visible = mask_dynamic_sql_visible(source)
    name_index = enclosing_object_name_index(clean)

    def _object_name_at(position: int) -> str:
        return enclosing_object_name(name_index, position)

    findings: list[Finding] = []
    schema_level_type_starts = _schema_level_create_type_positions(visible)

    for m in _LOCAL_COLLECTION_TYPE_RE.finditer(visible):
        if m.start() in schema_level_type_starts:
            continue
        findings.append(
            Finding(
                detector="bulk_collect",
                severity="high",
                object_name=_object_name_at(m.start()),
                line=line_at(visible, m.start()),
                snippet=m.group(0).strip(),
                message=_TYPE_DECL_MESSAGE,
            )
        )

    for m in _BULK_COLLECT_RE.finditer(visible):
        findings.append(
            Finding(
                detector="bulk_collect",
                severity="high",
                object_name=_object_name_at(m.start()),
                line=line_at(visible, m.start()),
                snippet=m.group(0).strip(),
                message=_BULK_COLLECT_MESSAGE,
            )
        )

    for m in _FORALL_RE.finditer(visible):
        findings.append(
            Finding(
                detector="bulk_collect",
                severity="high",
                object_name=_object_name_at(m.start()),
                line=line_at(visible, m.start()),
                snippet=m.group(0).strip(),
                message=_FORALL_MESSAGE,
            )
        )

    return findings
