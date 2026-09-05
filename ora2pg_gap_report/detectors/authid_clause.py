import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

_AUTHID_RE = re.compile(r"\bAUTHID\s+(CURRENT_USER|DEFINER)\b", re.IGNORECASE)

_DOC = """Detect Oracle's AUTHID CURRENT_USER / AUTHID DEFINER clause.
ora2pg silently drops the entire enclosing routine rather than
converting it -- no output, no error, not even a DEBUG log line. See
docs/research/gap-059-authid-clause.md."""

SPEC = DetectorSpec(
    name="authid_clause",
    dialect="oracle",
    severity="high",
    pattern=_AUTHID_RE,
    snippet=lambda m: " ".join(m.group(0).upper().split()),
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_authid_clauses = build(SPEC, plsql_lex)
find_authid_clauses.__doc__ = _DOC
