import re

from .. import mysql_lex
from ..detector_spec import DetectorSpec, build

# `LIMIT <offset>, <count>`. The two operands are matched as bare words
# rather than digits only, so the same construct written with procedure
# parameters (LIMIT p_offset, p_count -- just as common in stored code)
# is caught too; a plain `LIMIT n` has no comma and never matches.
_LIMIT_COMMA_RE = re.compile(r"\bLIMIT\s+\w+\s*,\s*\w+", re.IGNORECASE)

_DOC = """Detect MySQL/MariaDB's comma form of LIMIT (`LIMIT offset, count`).
ora2pg -m copies it through unchanged; PostgreSQL rejects the syntax
outright, and since bodies are not checked at load time the routine
fails on its first call. The argument order is reversed relative to
PostgreSQL's `LIMIT ... OFFSET`. See docs/research/
gap-075-mysql-limit-comma.md."""

SPEC = DetectorSpec(
    name="mysql_limit_comma",
    dialect="mysql",
    severity="high",
    pattern=_LIMIT_COMMA_RE,
    snippet='LIMIT n, m',
)

find_mysql_limit_comma = build(SPEC, mysql_lex)
find_mysql_limit_comma.__doc__ = _DOC
