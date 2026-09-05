import re

from .. import plsql_lex
from ..plsql_lex import IDENTIFIER
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

# SUBTYPE <name> IS <base type> RANGE <lo> .. <hi>. The RANGE part is
# required by the match: an unconstrained `SUBTYPE s IS PLS_INTEGER;`
# converts to a plain CREATE DOMAIN that loads correctly, and a
# `NOT NULL`-constrained one becomes a valid `CREATE DOMAIN ... NOT NULL`
# -- neither is a gap, so neither is flagged.
_SUBTYPE_RANGE_RE = re.compile(
    rf"\bSUBTYPE\s+({IDENTIFIER})\s+IS\s+[^;]*?\bRANGE\s+(-?\d+)\s*\.\.\s*(-?\d+)",
    re.IGNORECASE,
)

_DOC = """Detect PL/SQL SUBTYPE declarations carrying a RANGE constraint.
ora2pg turns them into CREATE DOMAIN but copies the RANGE clause
verbatim, which PostgreSQL's CREATE DOMAIN does not accept, so the
generated DDL fails to load. See
docs/research/gap-061-subtype-range.md."""

SPEC = DetectorSpec(
    name="subtype_range",
    dialect="oracle",
    severity="high",
    pattern=_SUBTYPE_RANGE_RE,
    snippet=lambda m: f"SUBTYPE {m.group(1).upper()} ... RANGE {m.group(2)} .. {m.group(3)}",
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_subtype_ranges = build(SPEC, plsql_lex)
find_subtype_ranges.__doc__ = _DOC
