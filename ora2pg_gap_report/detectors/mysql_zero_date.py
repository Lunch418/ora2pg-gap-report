import re

from ..models import Finding
from ..mysql_lex import (
    line_at,
    mask_comments_only,
    mask_strings_and_comments,
    qualified_name_pattern,
    table_column_definition_list,
)

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# MySQL's "zero" date/datetime sentinels, in the spellings that actually
# appear in dumps: a zero date, a zero datetime with or without the time
# part, and the same with a 'T' separator is deliberately NOT matched --
# it isn't a form MySQL itself emits.
_ZERO_DATE_RE = re.compile(
    r"'0000-00-00(?:\s+00:00:00)?'",
)

_MESSAGE = (
    "'0000-00-00' — «нулевая» дата MySQL/MariaDB: не настоящая дата, а "
    "признак «значение не задано», который MySQL допускает в DATE/DATETIME "
    "по историческим причинам. ora2pg (-m) молча подменяет её на "
    "'1970-01-01' — настоящую, осмысленную дату (начало эпохи Unix), — "
    "подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16 (docs/"
    "research/gap-083-mysql-zero-date.md): в сгенерированном DDL стоит "
    "DEFAULT '1970-01-01', и вставленная после миграции строка получает "
    "именно эту дату (проверено на живых данных). Ошибки нет ни на "
    "загрузке, ни потом — расхождение чисто смысловое и потому "
    "незаметное: запросы вида WHERE d = '0000-00-00' (поиск незаполненных) "
    "перестают находить что-либо, а отчёты по датам начинают показывать "
    "1970 год как реальное событие. Правильный перенос — NULL (плюс, если "
    "нужно, NOT NULL снимается) или отдельный признак «не задано»; "
    "проверьте заодно и сами данные, а не только DEFAULT."
)


def find_mysql_zero_dates(source: str) -> list[Finding]:
    """Detect MySQL/MariaDB's '0000-00-00' zero-date sentinel. ora2pg -m
    silently rewrites it to '1970-01-01' -- a real date -- with no error
    at any stage, so a "not set" marker becomes an actual value. Reads the
    comments-only view, since the sentinel lives inside a string literal
    that the fully-masked view blanks out. See docs/research/
    gap-083-mysql-zero-date.md."""
    clean = mask_strings_and_comments(source)
    visible = mask_comments_only(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        span = table_column_definition_list(clean, m.end())
        if span is None:
            continue  # bare CTAS with no column-definition list at all
        open_pos, close_pos = span
        # Same offsets in both views -- the two masking passes are
        # length-preserving by contract (see mysql_lex._mask).
        column_list = visible[open_pos + 1 : close_pos]

        for zero_match in _ZERO_DATE_RE.finditer(column_list):
            findings.append(
                Finding(
                    detector="mysql_zero_date",
                    severity="high",
                    object_name=m.group(1).upper(),
                    line=line_at(clean, open_pos + 1 + zero_match.start()),
                    snippet=zero_match.group(0),
                    message=_MESSAGE,
                )
            )

    return findings
