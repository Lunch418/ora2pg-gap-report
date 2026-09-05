import re

from .. import mysql_lex
from ..detector_spec import DetectorSpec, build

_HANDLER_RE = re.compile(
    r"\bDECLARE\s+(CONTINUE|EXIT|UNDO)\s+HANDLER\b",
    re.IGNORECASE,
)

_DOC = """Detect MySQL/MariaDB's DECLARE ... HANDLER condition handlers.
ora2pg -m drops them entirely, emitting no PL/pgSQL EXCEPTION block
in their place, so a routine's whole error-handling policy silently
disappears -- errors MySQL swallowed now propagate to the caller.
See docs/research/gap-084-mysql-declare-handler.md."""

SPEC = DetectorSpec(
    name="mysql_declare_handler",
    dialect="mysql",
    severity="high",
    pattern=_HANDLER_RE,
    snippet=lambda m: f"DECLARE {m.group(1).upper()} HANDLER",
)

find_mysql_declare_handlers = build(SPEC, mysql_lex)
find_mysql_declare_handlers.__doc__ = _DOC
