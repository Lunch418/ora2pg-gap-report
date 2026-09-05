import re

from .. import mysql_lex
from ..detector_spec import DetectorSpec, build

_DATE_FORMAT_RE = re.compile(r"\bDATE_FORMAT\s*\(", re.IGNORECASE)

_DOC = """Detect MySQL/MariaDB's DATE_FORMAT(). ora2pg -m emits a bare
parenthesised pair -- a row constructor -- with the to_char function
name missing entirely and %d left untranslated, so nothing errors at
any stage and the query silently returns a tuple instead of a
formatted string. See docs/research/gap-081-mysql-date-format.md."""

SPEC = DetectorSpec(
    name="mysql_date_format",
    dialect="mysql",
    severity="high",
    pattern=_DATE_FORMAT_RE,
    snippet='DATE_FORMAT(...)',
)

find_mysql_date_format = build(SPEC, mysql_lex)
find_mysql_date_format.__doc__ = _DOC
