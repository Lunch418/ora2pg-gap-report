import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

# A cursor *expression* -- CURSOR( immediately followed by a SELECT -- not
# a cursor *declaration* ('CURSOR c IS SELECT ...', which is an ordinary
# PL/SQL declaration ora2pg converts correctly and which must not be
# flagged here). The parenthesis directly after the keyword is what
# separates the two: a declaration always has an identifier there.
_CURSOR_EXPRESSION_RE = re.compile(r"\bCURSOR\s*\(\s*(?:\(\s*)*SELECT\b", re.IGNORECASE)

_DOC = """Detect Oracle's CURSOR(SELECT ...) cursor expression. ora2pg
copies it through unchanged and PostgreSQL has no equivalent, so the
generated query fails to parse. Deliberately does not match ordinary
'CURSOR c IS SELECT ...' declarations. See
docs/research/gap-055-cursor-expression.md."""

SPEC = DetectorSpec(
    name="cursor_expression",
    dialect="oracle",
    severity="high",
    pattern=_CURSOR_EXPRESSION_RE,
    snippet='CURSOR(SELECT',
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_cursor_expressions = build(SPEC, plsql_lex)
find_cursor_expressions.__doc__ = _DOC
