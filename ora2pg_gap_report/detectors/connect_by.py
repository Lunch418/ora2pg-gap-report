import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, skip_balanced_parens

_CONNECT_BY_RE = re.compile(r"\bCONNECT\s+BY\b", re.IGNORECASE)
_WITH_RECURSIVE_NAME_RE = re.compile(r"\bWITH\s+RECURSIVE\s+(\w+)\s+AS\s*\(", re.IGNORECASE)
_LEVEL_REF_RE = re.compile(r"(?<![A-Za-z0-9_$#])(?:\w+\.)?LEVEL\b", re.IGNORECASE)
# ora2pg always names the generated CTE "cte" regardless of the source
# query, so it's useless for identifying *which* function is affected in a
# report — find the nearest enclosing "CREATE [OR REPLACE] FUNCTION/
# PROCEDURE name" instead (ora2pg always emits one of these around a
# CONNECT BY conversion, package-scoped or standalone alike).
_ENCLOSING_ROUTINE_RE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:FUNCTION|PROCEDURE)\s+(\w+)",
    re.IGNORECASE,
)

# Object-type guess for the *Oracle source*, so the caller can pick the
# matching `ora2pg -t <TYPE>` mode instead of always assuming PACKAGE —
# CONNECT BY can just as well live in a standalone function/procedure.
_OBJECT_TYPE_PATTERNS = (
    (re.compile(r"\bPACKAGE\s+BODY\b", re.IGNORECASE), "PACKAGE"),
    (re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\b", re.IGNORECASE), "TRIGGER"),
    (re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?PROCEDURE\b", re.IGNORECASE), "PROCEDURE"),
    (re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\b", re.IGNORECASE), "FUNCTION"),
    (re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?VIEW\b", re.IGNORECASE), "VIEW"),
)

_MESSAGE = (
    "Сгенерированный ora2pg WITH RECURSIVE ссылается на LEVEL — псевдоколонку "
    "Oracle, которой нет ни в PostgreSQL, ни в самом CTE. ora2pg переименовывает "
    "LEVEL в столбец-счётчик глубины в анкорной ветке CTE, но не везде — "
    "известный баг подстановки его regex-based конвертера CONNECT BY "
    "(docs/research/step0-show-report-baseline.md, раздел 3; воспроизведено "
    "на реальном прогоне ora2pg). Сгенерированный SQL в этом виде не "
    "выполнится в PostgreSQL без ручной правки — LEVEL нужно заменить на "
    "настоящее имя колонки-счётчика."
)


def has_connect_by(source: str) -> bool:
    """Cheap pre-check on the *Oracle source*: is it worth spending an
    ora2pg subprocess call on this file for a CONNECT BY conversion-quality
    check at all?"""
    return bool(_CONNECT_BY_RE.search(mask_strings_and_comments(source)))


def guess_object_type(source: str) -> str:
    """Which `ora2pg -t <TYPE>` mode to run against this file. Checked in
    order of specificity — a PACKAGE BODY containing CREATE FUNCTION text
    (unlikely but not impossible in comments/strings, already masked out
    here) must still resolve to PACKAGE, not FUNCTION."""
    clean = mask_strings_and_comments(source)
    for pattern, object_type in _OBJECT_TYPE_PATTERNS:
        if pattern.search(clean):
            return object_type
    return "PACKAGE"  # fallback: the most common shape in this project's scope


def find_connect_by_risks(ora2pg_output: str) -> list[Finding]:
    """Lint ora2pg's *generated* SQL (not the Oracle source) for a specific,
    confirmed ora2pg bug: a WITH RECURSIVE body that still references the
    Oracle-only LEVEL pseudocolumn instead of the depth counter ora2pg
    itself introduces in the anchor branch. Unlike the other three
    detectors (which analyze Oracle source directly), this one's input is
    ora2pg's own output — see ora2pg_gap_report/ora2pg_wrapper.run_estimate_cost().

    ora2pg's own cost estimator already counts CONNECT BY correctly (see
    step0-show-report-baseline.md section 3) — the gap this closes isn't
    "was CONNECT BY seen", it's "is the conversion it produced actually
    valid SQL".
    """
    clean = mask_strings_and_comments(ora2pg_output)
    routine_matches = list(_ENCLOSING_ROUTINE_RE.finditer(clean))
    findings: list[Finding] = []

    for m in _WITH_RECURSIVE_NAME_RE.finditer(clean):
        cte_name = m.group(1)
        paren_start = m.end() - 1
        paren_end = skip_balanced_parens(clean, paren_start)
        body = clean[paren_start:paren_end]

        level_match = _LEVEL_REF_RE.search(body)
        if not level_match:
            continue

        absolute_pos = paren_start + level_match.start()
        object_name = _enclosing_routine_name(routine_matches, m.start()) or cte_name
        findings.append(
            Finding(
                detector="connect_by",
                severity="high",
                object_name=object_name.upper(),
                line=line_at(clean, absolute_pos),
                snippet=level_match.group(0).strip(),
                message=_MESSAGE,
            )
        )

    return findings


def _enclosing_routine_name(routine_matches: list, position: int):
    name = None
    for m in routine_matches:
        if m.start() > position:
            break
        name = m.group(1)
    return name
