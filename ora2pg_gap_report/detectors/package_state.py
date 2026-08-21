import re

from ..models import Finding
from ..plsql_lex import (
    IDENTIFIER,
    PACKAGE_BODY_NAME_RE,
    PACKAGE_SPEC_NAME_RE,
    ROUTINE_START_RE,
    line_at,
    mask_strings_and_comments,
)

_IS_AS_RE = re.compile(r"\b(?:IS|AS)\b", re.IGNORECASE)
# Bounds a package *spec*'s own declare section the same way ROUTINE_START_RE
# bounds a package body's: the first subprogram declaration ends it. A spec
# subprogram is just a prototype ('PROCEDURE name(...);' or 'FUNCTION
# name(...) RETURN type;', no IS/AS/body) -- ROUTINE_START_RE itself
# requires a trailing IS/AS, so it doesn't match these at all.
_SUBPROGRAM_DECL_RE = re.compile(r"\b(?:PROCEDURE|FUNCTION)\b", re.IGNORECASE)

# A reasonably common set of Oracle scalar types (plus the %TYPE-anchored
# form) -- not exhaustive, deliberately: the goal is catching the common
# real-world shape of package-level "context" state (an ID, a flag, a
# cached value), not parsing every possible Oracle datatype. A package-
# level TYPE/CURSOR/EXCEPTION/SUBTYPE/PRAGMA declaration is excluded by
# construction -- none of those match this shape at all, and none of
# them are what ora2pg's set_config/current_setting rewrite applies to.
_SCALAR_TYPES = (
    r"NUMBER|VARCHAR2|VARCHAR|INTEGER|PLS_INTEGER|BINARY_INTEGER|"
    r"BOOLEAN|DATE|TIMESTAMP|CHAR|NCHAR|CLOB|RAW|LONG"
)
# Oracle's own grammar is 'name type [NOT NULL] {:= | DEFAULT} expr;' or
# just 'name type;' with no initializer at all -- NOT NULL, if present,
# comes before the initializer keyword, not instead of it, so it's an
# optional group ahead of the (':=' | 'DEFAULT' | ';') alternation, not
# an alternative to it.
_PACKAGE_VAR_RE = re.compile(
    rf"^[ \t]*({IDENTIFIER})\s+(?:CONSTANT\s+)?(?:(?:{_SCALAR_TYPES})(?:\s*\([^)]*\))?|{IDENTIFIER}(?:\.{IDENTIFIER})?%TYPE)"
    rf"\s*(?:NOT\s+NULL\s*)?(?::=|DEFAULT\b|;)",
    re.IGNORECASE | re.MULTILINE,
)

_MESSAGE = (
    "Переменная, объявленная на верхнем уровне PACKAGE BODY (не внутри "
    "конкретной процедуры/функции) — состояние на уровне сессии, общее "
    "для всех процедур пакета. ora2pg заменяет чтение/запись такой "
    "переменной на current_setting()/set_config() с пользовательским GUC-"
    "параметром — идея разумная (третий аргумент set_config — false, что "
    "соответствует времени жизни пакетной переменной в Oracle, вся "
    "сессия), но реализация сломана в двух местах (подтверждено реальным "
    "прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-036-package-state.md). Во-первых, set_config() "
    "принимает text вторым аргументом, а ora2pg не добавляет явное "
    "приведение типа для нетекстовых переменных — 'ERROR: function "
    "set_config(unknown, bigint, boolean) does not exist' при любом "
    "вызове записывающей процедуры, без исключений. Во-вторых, даже "
    "после ручного добавления приведения типа: необъявленная числовая "
    "пакетная переменная в Oracle по умолчанию NULL, а чтение ещё не "
    "установленного пользовательского GUC-параметра в PostgreSQL "
    "завершается ошибкой 'unrecognized configuration parameter', а не "
    "NULL — проявляется, когда чтение происходит раньше первой записи в "
    "той же сессии. Нужно вручную добавить приведение типа к set_config() "
    "и missing_ok => true к current_setting(), либо спроектировать "
    "состояние иначе (временная таблица, параметр приложения)."
)


def _scan_declare_section(
    clean: str, declare_text: str, offset: int, package_name: str
) -> list[Finding]:
    return [
        Finding(
            detector="package_state",
            severity="high",
            object_name=f"{package_name}.{var_match.group(1).upper()}",
            line=line_at(clean, offset + var_match.start()),
            snippet=re.sub(r"\s+", " ", var_match.group(0).strip()),
            message=_MESSAGE,
        )
        for var_match in _PACKAGE_VAR_RE.finditer(declare_text)
    ]


def find_package_state(source: str) -> list[Finding]:
    """Detect a scalar variable declared at package top level (not inside
    any member routine's own declare section) -- Oracle's session-scoped
    package state. ora2pg rewrites reads/writes of such a variable into
    current_setting()/set_config() calls against a custom GUC parameter,
    but the rewrite has two confirmed bugs: set_config() is called with
    no explicit ::text cast (breaks on the very first call for any
    non-text variable), and current_setting() has no missing_ok => true
    (breaks differently from Oracle's own NULL-default semantics for a
    variable read before ever being set in the same session). See
    docs/research/gap-036-package-state.md.

    Covers both a PACKAGE BODY's own top-level declare section (private
    state, no member visible outside the package) and a PACKAGE spec's
    (public state) -- ora2pg's rewrite applies to package-level variables
    regardless of which one declares them, and DBMS_METADATA.GET_DDL
    routinely exports them as two separate files, so a detector that only
    ever looked at the body would never see a spec-only .pks export at
    all. GAP-036's own documented minimal example declares its variable
    in the spec, with an empty body declare section -- confirmed missing
    entirely before this covered the spec too.

    Each container's own top-level declare section is bounded by
    whichever comes first: the first member declaration after its own
    IS/AS (ROUTINE_START_RE for a body's first routine *body*,
    _SUBPROGRAM_DECL_RE for a spec's first routine *prototype* -- a spec
    entry has no IS/AS of its own for ROUTINE_START_RE to match), or the
    next package container of either kind (statement_end()-style
    bounding, same reasoning as read_only_table.py -- without this, a
    package with no member routines at all would let the declare-section
    search run unbounded into a later, unrelated package's own
    declarations, misattributing its variables to the wrong package).
    Everything before that boundary is package-level state -- a
    deliberate simplification for a heuristic tool: Oracle allows
    interleaving declarations and routines within a package, but that
    ordering is rare in practice, and declarations after the first
    member routine are out of scope here rather than risked as a false
    positive.

    Uses PACKAGE_BODY_NAME_RE/PACKAGE_SPEC_NAME_RE (plsql_lex's own
    canonical matchers, EDITIONABLE/NONEDITIONABLE included) rather than
    detector-local reimplementations, and looks up each package's own
    name directly from its own match rather than via
    enclosing_object_name_index() -- standalone routines/triggers/views
    are irrelevant to this detector's own scope, so building that
    shared, heavier multi-regex index just for a package-name lookup
    this detector can already do locally would be pure overhead."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    body_matches = list(PACKAGE_BODY_NAME_RE.finditer(clean))
    spec_matches = list(PACKAGE_SPEC_NAME_RE.finditer(clean))
    # Every package container's (spec or body) start position, sorted --
    # a shared upper bound so a spec with no member routines of its own
    # doesn't let its declare-section search run past its own END into a
    # later, unrelated package's declarations (of either kind).
    container_starts = sorted(m.start() for m in body_matches + spec_matches)

    def next_boundary(after: int) -> int:
        for pos in container_starts:
            if pos > after:
                return pos
        return len(clean)

    for pkg_match in body_matches:
        is_as = _IS_AS_RE.search(clean, pkg_match.end())
        if is_as is None:
            continue
        boundary = next_boundary(pkg_match.start())
        first_routine = ROUTINE_START_RE.search(clean, is_as.end(), boundary)
        declare_end = first_routine.start() if first_routine else boundary
        declare_text = clean[is_as.end() : declare_end]
        package_name = pkg_match.group(1).upper()
        findings.extend(_scan_declare_section(clean, declare_text, is_as.end(), package_name))

    for pkg_match in spec_matches:
        is_as = _IS_AS_RE.search(clean, pkg_match.end())
        if is_as is None:
            continue
        boundary = next_boundary(pkg_match.start())
        first_subprogram = _SUBPROGRAM_DECL_RE.search(clean, is_as.end(), boundary)
        declare_end = first_subprogram.start() if first_subprogram else boundary
        declare_text = clean[is_as.end() : declare_end]
        package_name = pkg_match.group(1).upper()
        findings.extend(_scan_declare_section(clean, declare_text, is_as.end(), package_name))

    return findings
