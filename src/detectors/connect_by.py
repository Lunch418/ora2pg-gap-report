import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, skip_balanced_parens

_CONNECT_BY_RE = re.compile(r"\bCONNECT\s+BY\b", re.IGNORECASE)
_WITH_RECURSIVE_NAME_RE = re.compile(r"\bWITH\s+RECURSIVE\s+(\w+)\s+AS\s*\(", re.IGNORECASE)
_LEVEL_REF_RE = re.compile(r"(?<![A-Za-z0-9_$#])(?:\w+\.)?LEVEL\b", re.IGNORECASE)

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


def find_connect_by_risks(ora2pg_output: str) -> list[Finding]:
    """Lint ora2pg's *generated* SQL (not the Oracle source) for a specific,
    confirmed ora2pg bug: a WITH RECURSIVE body that still references the
    Oracle-only LEVEL pseudocolumn instead of the depth counter ora2pg
    itself introduces in the anchor branch. Unlike the other three
    detectors (which analyze Oracle source directly), this one's input is
    ora2pg's own output — see src/ora2pg_wrapper.run_estimate_cost().

    ora2pg's own cost estimator already counts CONNECT BY correctly (see
    step0-show-report-baseline.md section 3) — the gap this closes isn't
    "was CONNECT BY seen", it's "is the conversion it produced actually
    valid SQL".
    """
    clean = mask_strings_and_comments(ora2pg_output)
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
        findings.append(
            Finding(
                detector="connect_by",
                severity="high",
                object_name=cte_name.upper(),
                line=line_at(clean, absolute_pos),
                snippet=level_match.group(0).strip(),
                message=_MESSAGE,
            )
        )

    return findings
