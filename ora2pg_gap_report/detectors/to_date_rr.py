import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_comments_only,
    mask_strings_and_comments,
)

# TO_DATE/TO_TIMESTAMP whose format model contains RR or RRRR. The format
# model is a string literal, so this is one of the two detectors that run
# against mask_comments_only(): mask_strings_and_comments() would blank
# the very text being matched. The call keyword is still required in front
# of the literal, so a bare 'RR' inside an unrelated string (a message, a
# column comment) is not enough to trigger a finding. RRRR is included
# because it is the same Oracle-only family of format code -- PostgreSQL
# knows neither.
_TO_DATE_RR_RE = re.compile(
    r"\bTO_(?:DATE|TIMESTAMP(?:_TZ)?)\s*\([^;()]*?'[^']*\bRR(?:RR)?\b[^']*'",
    re.IGNORECASE,
)

_MESSAGE = (
    "TO_DATE/TO_TIMESTAMP с форматом RR — Oracle-специфичный код "
    "двузначного года с «поворотным» правилом: 00-49 читается как 20xx, "
    "50-99 как 19xx. ora2pg оставляет RR в строке формата как есть "
    "(подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, "
    "docs/research/gap-058-to-date-rr.md). PostgreSQL такого кода формата "
    "не знает и, что хуже всего, не ругается на него: "
    "to_date('85-06-01','RR-MM-DD') молча возвращает 0001-06-01 BC — "
    "первый год до нашей эры вместо 1985 года. Ошибки нет ни на загрузке, "
    "ни на выполнении, данные просто оказываются неверными. Заменять нужно "
    "на явный четырёхзначный YYYY с приведением входных данных: YY тут не "
    "эквивалент, хотя выглядит им. Пороги у правил разные — у Oracle RR "
    "это 00-49 → 20xx, 50-99 → 19xx, а у PostgreSQL YY это 00-69 → 20xx, "
    "70-99 → 19xx (проверено на PostgreSQL 16). Совпадают они только на "
    "00-49 и 70-99, а на 50-69 расходятся ровно на сто лет: '65' по "
    "Oracle это 1965 год, а по YY в PostgreSQL — 2065. "
    "Отдельно стоит отметить асимметрию в самом ora2pg: в TO_CHAR он RR "
    "на YY заменяет, а в TO_DATE — нет."
)


def find_to_date_rr(source: str) -> list[Finding]:
    """Detect Oracle's RR/RRRR two-digit-year format code inside a
    TO_DATE/TO_TIMESTAMP format model. ora2pg leaves it in place;
    PostgreSQL does not recognise it and silently produces year 1 BC
    instead of raising anything. See
    docs/research/gap-058-to-date-rr.md.

    Matched against mask_comments_only() rather than the usual fully
    masked view, because the format model this is about *is* a string
    literal -- while commented-out code still must not match."""
    clean = mask_strings_and_comments(source)
    literals = mask_comments_only(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _TO_DATE_RR_RE.finditer(literals):
        findings.append(
            Finding(
                detector="to_date_rr",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=m.group(0).split("(")[0].strip().upper() + "(... 'RR' ...)",
                message=_MESSAGE,
            )
        )

    return findings
