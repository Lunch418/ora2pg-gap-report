import re

from ..models import Finding

_PACKAGE_BODY_NAME_RE = re.compile(
    r"PACKAGE\s+BODY\s+(?:\"?\w+\"?\.)?\"?(\w+)\"?",
    re.IGNORECASE,
)
_ROUTINE_START_RE = re.compile(
    r"^\s*(?:FUNCTION|PROCEDURE)\s+(\w+)",
    re.IGNORECASE | re.MULTILINE,
)
_IS_AS_RE = re.compile(r"\b(?:IS|AS)\b", re.IGNORECASE)
_BEGIN_RE = re.compile(r"\bBEGIN\b", re.IGNORECASE)
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


def _strip_comments(source: str) -> str:
    without_block = re.sub(
        r"/\*.*?\*/",
        lambda m: "\n" * m.group(0).count("\n"),
        source,
        flags=re.DOTALL,
    )
    return re.sub(r"--[^\n]*", "", without_block)


def _skip_balanced_parens(text: str, start: int) -> int:
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)


def _declare_section(source: str, routine_name_end: int, boundary: int) -> str | None:
    """Text between a routine's IS/AS and its BEGIN, bounded by the next
    routine's start. Returns None for forward declarations with no body."""
    pos = routine_name_end
    while pos < boundary and source[pos] in " \t\r\n":
        pos += 1
    if pos < boundary and source[pos] == "(":
        pos = _skip_balanced_parens(source, pos)
    is_as = _IS_AS_RE.search(source, pos, boundary)
    if not is_as:
        return None
    begin = _BEGIN_RE.search(source, is_as.end(), boundary)
    if not begin:
        return None
    return source[is_as.end() : begin.start()], is_as.end()


def find_autonomous_transactions(source: str) -> list[Finding]:
    """Detect PRAGMA AUTONOMOUS_TRANSACTION inside top-level functions and
    procedures of a PACKAGE BODY. Does not descend into locally nested
    functions/procedures (declared inside another routine's declare
    section) — that is a separate, smaller ora2pg gap, out of scope here.
    """
    clean = _strip_comments(source)

    package_match = _PACKAGE_BODY_NAME_RE.search(clean)
    package_name = package_match.group(1).upper() if package_match else "UNKNOWN"

    routine_matches = list(_ROUTINE_START_RE.finditer(clean))
    findings: list[Finding] = []

    for idx, match in enumerate(routine_matches):
        routine_name = match.group(1)
        boundary = (
            routine_matches[idx + 1].start()
            if idx + 1 < len(routine_matches)
            else len(clean)
        )
        result = _declare_section(clean, match.end(), boundary)
        if result is None:
            continue
        declare_text, declare_start = result

        pragma_match = _PRAGMA_RE.search(declare_text)
        if not pragma_match:
            continue

        absolute_pos = declare_start + pragma_match.start()
        line_no = clean.count("\n", 0, absolute_pos) + 1

        findings.append(
            Finding(
                detector="autonomous_tx",
                severity="high",
                object_name=f"{package_name}.{routine_name.upper()}",
                line=line_no,
                snippet=pragma_match.group(0).strip(),
                message=_MESSAGE,
            )
        )

    return findings
