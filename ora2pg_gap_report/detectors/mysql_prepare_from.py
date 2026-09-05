import re

from .. import mysql_lex
from ..detector_spec import DetectorSpec, build

# `PREPARE <name> FROM ...`. The FROM keyword is what distinguishes
# MySQL's spelling from PostgreSQL's own PREPARE (`PREPARE name AS
# query`), which is valid and must not be flagged -- ora2pg's output can
# legitimately contain the latter.
_PREPARE_FROM_RE = re.compile(r"\bPREPARE\s+\w+\s+FROM\b", re.IGNORECASE)

_DOC = """Detect MySQL/MariaDB's `PREPARE <name> FROM <string>`. PostgreSQL
spells its own PREPARE differently (`PREPARE name AS query`, taking
SQL text rather than a string variable), so ora2pg -m's verbatim copy
fails on the first call with a syntax error at FROM. PL/pgSQL's
EXECUTE is the actual equivalent. See docs/research/
gap-078-mysql-prepare-from.md."""

SPEC = DetectorSpec(
    name="mysql_prepare_from",
    dialect="mysql",
    severity="high",
    pattern=_PREPARE_FROM_RE,
    snippet='PREPARE ... FROM',
)

find_mysql_prepare_from = build(SPEC, mysql_lex)
find_mysql_prepare_from.__doc__ = _DOC
