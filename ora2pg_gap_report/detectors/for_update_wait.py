import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

# Oracle's WAIT <n> lock-timeout clause on FOR UPDATE. Anchored on FOR
# UPDATE (with an optional `OF <column list>` in between) rather than on
# the bare word WAIT, which is an ordinary identifier. NOWAIT is
# deliberately not matched: PostgreSQL spells it the same way and ora2pg
# passes it through correctly, so only the numeric-timeout form is a gap.
_FOR_UPDATE_WAIT_RE = re.compile(
    r"\bFOR\s+UPDATE\b(?:\s+OF\b[^;()]*?)?\s+WAIT\s+\d+",
    re.IGNORECASE,
)

_DOC = """Detect Oracle's FOR UPDATE ... WAIT n lock-timeout clause. ora2pg
passes it through unchanged; PostgreSQL supports only NOWAIT and SKIP
LOCKED there, so the generated query fails to parse. See
docs/research/gap-056-for-update-wait.md."""

SPEC = DetectorSpec(
    name="for_update_wait",
    dialect="oracle",
    severity="high",
    pattern=_FOR_UPDATE_WAIT_RE,
    snippet=lambda m: " ".join(m.group(0).upper().split()),
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_for_update_wait = build(SPEC, plsql_lex)
find_for_update_wait.__doc__ = _DOC
