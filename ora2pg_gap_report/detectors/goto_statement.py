import re

from .. import plsql_lex
from ..plsql_lex import IDENTIFIER
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

# GOTO followed by a label name. The label name is required by the match
# so that the word alone -- as a column, a variable or part of an
# identifier -- is not enough to produce a finding.
_GOTO_RE = re.compile(rf"\bGOTO\s+({IDENTIFIER})", re.IGNORECASE)

_DOC = """Detect PL/SQL GOTO statements. ora2pg copies them through
unchanged and PL/pgSQL has no GOTO at all, so the procedure loads
cleanly (bodies are not checked) and then fails on its first call.
See docs/research/gap-063-goto-statement.md."""

SPEC = DetectorSpec(
    name="goto_statement",
    dialect="oracle",
    severity="high",
    pattern=_GOTO_RE,
    snippet=lambda m: f"GOTO {m.group(1).lower()}",
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_goto_statements = build(SPEC, plsql_lex)
find_goto_statements.__doc__ = _DOC
