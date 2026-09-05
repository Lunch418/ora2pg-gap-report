import re

from .. import plsql_lex
from ..plsql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, MATCH_NAMED, build

_CONTEXT_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+(?:OR\s+REPLACE\s+)?CONTEXT"),
    re.IGNORECASE,
)

_DOC = """Detect Oracle CREATE CONTEXT declarations. ora2pg has no
conversion path for these at all -- see
docs/research/gap-015-context.md."""

SPEC = DetectorSpec(
    name="context_object",
    dialect="oracle",
    severity="medium",
    pattern=_CONTEXT_RE,
    strategy=MATCH_NAMED,
    snippet='CREATE CONTEXT',
)

find_context_declarations = build(SPEC, plsql_lex)
find_context_declarations.__doc__ = _DOC
