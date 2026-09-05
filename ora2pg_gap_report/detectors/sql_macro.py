import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

_SQL_MACRO_RE = re.compile(r"\bSQL_MACRO\b", re.IGNORECASE)

_DOC = """Detect Oracle's SQL_MACRO function modifier. ora2pg drops the
keyword and converts the function into an ordinary PL/pgSQL function
returning a string -- it compiles fine, but fails with a type error at
any call site that uses it the way Oracle intended (inline SQL
expression substitution, e.g. as a boolean expression directly in a
WHERE clause). See docs/research/gap-019-sql-macro.md."""

SPEC = DetectorSpec(
    name="sql_macro",
    dialect="oracle",
    severity="high",
    pattern=_SQL_MACRO_RE,
    snippet='SQL_MACRO',
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_sql_macros = build(SPEC, plsql_lex)
find_sql_macros.__doc__ = _DOC
