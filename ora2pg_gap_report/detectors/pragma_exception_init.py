import re

from .. import plsql_lex
from ..plsql_lex import IDENTIFIER
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

_PRAGMA_EXCEPTION_INIT_RE = re.compile(
    rf"\bPRAGMA\s+EXCEPTION_INIT\s*\(\s*({IDENTIFIER})\s*,\s*(-?\d+)\s*\)",
    re.IGNORECASE,
)

_DOC = """Detect Oracle's PRAGMA EXCEPTION_INIT. ora2pg drops the pragma and
rewrites the matching handler to a fixed placeholder SQLSTATE
('50001') that PostgreSQL never raises, so the handler silently stops
firing and the error escapes at runtime. See
docs/research/gap-060-pragma-exception-init.md."""

SPEC = DetectorSpec(
    name="pragma_exception_init",
    dialect="oracle",
    severity="high",
    pattern=_PRAGMA_EXCEPTION_INIT_RE,
    snippet=lambda m: f"PRAGMA EXCEPTION_INIT({m.group(1).upper()}, {m.group(2)})",
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_pragma_exception_init = build(SPEC, plsql_lex)
find_pragma_exception_init.__doc__ = _DOC
