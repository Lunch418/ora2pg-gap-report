import re

from ..models import Finding
from ..plsql_lex import (
    ROUTINE_START_RE,
    declare_and_begin,
    find_matching_end,
    mask_strings_and_comments,
    own_declare_text,
    qualified_name_pattern,
)

_PACKAGE_BODY_NAME_RE = re.compile(
    qualified_name_pattern(r"PACKAGE\s+BODY"),
    re.IGNORECASE,
)
_PRAGMA_RE = re.compile(r"PRAGMA\s+AUTONOMOUS_TRANSACTION\s*;", re.IGNORECASE)

_MESSAGE = (
    "ora2pg перенесёт эту процедуру/функцию через dblink-обёртку "
    "(переименует в *_atx, уберёт COMMIT из тела, добавит функцию-прокси, "
    "вызывающую её через dblink()). Стратегия рабочая, но не бесшовная: "
    "требуется расширение dblink и ручная настройка connection string — "
    "то есть сетевая зависимость между процедурами, которая может быть "
    "неприемлема в контуре с жёсткими требованиями к изоляции. При этом "
    "SHOW_REPORT и --estimate_cost систематически недооценивают стоимость "
    "этой конструкции именно для функций/процедур внутри PACKAGE BODY — "
    "сама PRAGMA стоит в декларативной секции (до BEGIN), которая не "
    "попадает в подсчёт стоимости (declare/code split в "
    "Ora2Pg.pm::_lookup_function)."
)


def _package_name_at(package_matches: list, position: int) -> str:
    name = "UNKNOWN"
    for pm in package_matches:
        if pm.start() > position:
            break
        name = pm.group(1).upper()
    return name


def find_autonomous_transactions(source: str) -> list[Finding]:
    """Detect PRAGMA AUTONOMOUS_TRANSACTION inside PACKAGE BODY routines.

    Handles multiple package bodies in one file, string/comment-aware
    scanning, and correctly excludes locally nested subprograms' own
    declare sections from their enclosing routine's — a nested routine's
    PRAGMA is neither dropped nor misattributed to the outer routine, it is
    simply out of scope (detecting *those* is a separate, smaller gap).
    """
    clean = mask_strings_and_comments(source)
    package_matches = list(_PACKAGE_BODY_NAME_RE.finditer(clean))

    findings: list[Finding] = []
    cursor = 0
    hard_boundary = len(clean)

    for match in ROUTINE_START_RE.finditer(clean):
        if match.start() < cursor:
            continue  # nested inside a routine already resolved below

        resolved = declare_and_begin(clean, match.end(), hard_boundary)
        if resolved is None:
            continue
        declare_start, begin_pos, nested_spans = resolved

        end_pos = find_matching_end(clean, begin_pos, hard_boundary)
        if end_pos is None:
            continue
        cursor = end_pos

        declare_text = own_declare_text(clean, declare_start, begin_pos, nested_spans)
        pragma_match = _PRAGMA_RE.search(declare_text)
        if not pragma_match:
            continue

        absolute_pos = declare_start + pragma_match.start()
        line_no = clean.count("\n", 0, absolute_pos) + 1
        package_name = _package_name_at(package_matches, match.start())

        findings.append(
            Finding(
                detector="autonomous_tx",
                severity="high",
                object_name=f"{package_name}.{match.group(1).upper()}",
                line=line_no,
                snippet=pragma_match.group(0).strip(),
                message=_MESSAGE,
            )
        )

    return findings
