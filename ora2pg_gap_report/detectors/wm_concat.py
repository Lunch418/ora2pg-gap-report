import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

# Both the bare and the SYS/WMSYS-qualified spellings, since legacy code
# uses all three interchangeably.
_WM_CONCAT_RE = re.compile(
    r"\b(?:(?:SYS|WMSYS)\s*\.\s*)?WM_CONCAT\s*\(",
    re.IGNORECASE,
)

_DOC = """Detect Oracle's undocumented WM_CONCAT aggregate. ora2pg copies
the call through unchanged (unlike LISTAGG, which it rewrites to
string_agg), and PostgreSQL has no such function, so the query fails
at run time. See docs/research/gap-065-wm-concat.md."""

SPEC = DetectorSpec(
    name="wm_concat",
    dialect="oracle",
    severity="high",
    pattern=_WM_CONCAT_RE,
    snippet='WM_CONCAT(',
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_wm_concat = build(SPEC, plsql_lex)
find_wm_concat.__doc__ = _DOC
