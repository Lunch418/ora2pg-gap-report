import re

from ..models import Finding
from ..plsql_lex import IDENTIFIER, line_at, mask_strings_and_comments

# A plain \b boundary would treat '$'/'#' as non-word, so e.g.
# "MY_PKG$UTL_FILE" would be misread as a real UTL_FILE reference — use a
# lookbehind consistent with plsql_lex.IDENTIFIER's character set instead.
_CALL_RE = re.compile(
    rf"(?<![A-Za-z0-9_$#])(DBMS_[A-Za-z0-9_$#]*|UTL_[A-Za-z0-9_$#]*)\.({IDENTIFIER})",
    re.IGNORECASE,
)

# Calls ora2pg genuinely rewrites to a working PostgreSQL equivalent
# (confirmed in docs/research/step0-show-report-baseline.md, section 4).
# Anything not listed here is treated as unsupported by default — that
# default is intentional: the research showed the overwhelming majority of
# DBMS_*/UTL_* usage has no targeted conversion, so "unknown" should read
# as "needs review", not "probably fine".
#
# This list is a snapshot pinned to the ora2pg version this project
# researches against (see gap_registry.py's ora2pg_version field), not a
# live check against the installed ora2pg's actual behavior. It only ever
# grows by someone re-running the same research method (real ora2pg, real
# PostgreSQL, real generated code) on a new call — nothing here re-verifies
# it automatically against a newer ora2pg release. The safe-by-construction
# direction still holds for anything *not* on this list (unknown defaults
# to flagged, not silently accepted), but a call that's already on this
# list would go silently unflagged even if a future ora2pg version
# regressed its conversion for it. Maintaining this list by hand as ora2pg
# evolves is a real, ongoing cost of this detector, not a one-time one.
_CONVERTED = {
    "DBMS_OUTPUT.PUT_LINE": "заменяется на вывод через встроенный ora2pg-хелпер (RAISE NOTICE-подобный механизм).",
    "DBMS_OUTPUT.PUT": "заменяется тем же хелпером, что и DBMS_OUTPUT.PUT_LINE.",
    "DBMS_OUTPUT.NEW_LINE": "заменяется тем же хелпером, что и DBMS_OUTPUT.PUT_LINE.",
    "DBMS_OUTPUT.ENABLE": "просто комментируется — поведение теряется, но код не ломается.",
    "DBMS_OUTPUT.DISABLE": "просто комментируется — поведение теряется, но код не ломается.",
    "DBMS_LOB.GETLENGTH": "заменяется на octet_length().",
    "DBMS_LOB.SUBSTR": "заменяется на substr() с перестановкой аргументов.",
}

_UNSUPPORTED_MESSAGE = (
    "Специальной конвертации в ora2pg для этого конкретного вызова не "
    "найдено (проверено по исходникам Ora2Pg/PLSQL.pm на шаге 0) — он "
    "попадёт только в обезличенный счётчик DBMS_/UTL_ (вес 3 в "
    "estimate_cost), а сам код останется как есть и не скомпилируется в "
    "PostgreSQL без ручного переписывания или подключения расширения orafce "
    "(если для этой функции там вообще есть эквивалент)."
)


def find_dbms_utl_calls(source: str) -> list[Finding]:
    """Classify DBMS_*/UTL_* references: flag only the ones ora2pg has no
    targeted conversion for. Calls ora2pg already handles (see _CONVERTED)
    are not reported — they're not a gap, SHOW_REPORT's generic DBMS_/UTL_
    counter already covers "is this package used at all" adequately; the
    value here is telling the two apart.
    """
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _CALL_RE.finditer(clean):
        object_name = f"{m.group(1).upper()}.{m.group(2).upper()}"
        if object_name in _CONVERTED:
            continue

        line_no = line_at(clean, m.start())
        findings.append(
            Finding(
                detector="dbms_utl_calls",
                severity="medium",
                object_name=object_name,
                line=line_no,
                snippet=m.group(0),
                message=_UNSUPPORTED_MESSAGE,
            )
        )

    return findings
