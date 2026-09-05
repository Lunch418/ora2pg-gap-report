import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

# CONNECT_BY_ROOT is an operator (prefix, applied to an expression),
# CONNECT_BY_ISLEAF/CONNECT_BY_ISCYCLE are pseudocolumns -- all three are
# copied verbatim by ora2pg and all three break the same way. Deliberately
# does NOT match SYS_CONNECT_BY_PATH: ora2pg genuinely converts that one
# into a working string concatenation inside the recursive CTE it builds
# (verified separately, see the research doc) -- flagging it would be a
# false positive on a construct that actually migrates fine.
_PSEUDOCOLUMN_RE = re.compile(
    r"\b(CONNECT_BY_ROOT|CONNECT_BY_ISLEAF|CONNECT_BY_ISCYCLE)\b",
    re.IGNORECASE,
)

_DOC = """Detect Oracle's CONNECT_BY_ROOT operator and the
CONNECT_BY_ISLEAF/CONNECT_BY_ISCYCLE pseudocolumns. ora2pg rewrites
the surrounding CONNECT BY into a WITH RECURSIVE but carries these
three through unchanged, so the generated code fails to load.
SYS_CONNECT_BY_PATH is deliberately excluded -- ora2pg does convert
that one correctly. See
docs/research/gap-039-connect-by-pseudocolumn.md."""

SPEC = DetectorSpec(
    name="connect_by_pseudocolumn",
    dialect="oracle",
    severity="high",
    pattern=_PSEUDOCOLUMN_RE,
    snippet=lambda m: m.group(1).upper(),
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_connect_by_pseudocolumns = build(SPEC, plsql_lex)
find_connect_by_pseudocolumns.__doc__ = _DOC
