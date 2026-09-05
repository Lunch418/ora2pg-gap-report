import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, build

# Anchored on the clause's own opening paren: ACCESSIBLE BY is always
# followed by a parenthesised accessor list. Excludes a double-quoted
# identifier literally named "ACCESSIBLE BY" -- mask_strings_and_comments()
# never masks double-quoted identifiers, so the text survives with its
# quotes intact, same guard as index_organized_table.py uses.
_ACCESSIBLE_BY_RE = re.compile(r'(?<!")\bACCESSIBLE\s+BY\s*\(', re.IGNORECASE)

_DOC = """Detect Oracle's ACCESSIBLE BY whitelist clause on a subprogram.
ora2pg copies it verbatim into the generated CREATE FUNCTION/PROCEDURE
header, where PostgreSQL rejects it with a syntax error at load time.
See docs/research/gap-043-accessible-by.md."""

SPEC = DetectorSpec(
    name="accessible_by",
    dialect="oracle",
    severity="high",
    pattern=_ACCESSIBLE_BY_RE,
    snippet='ACCESSIBLE BY',
)

find_accessible_by = build(SPEC, plsql_lex)
find_accessible_by.__doc__ = _DOC
