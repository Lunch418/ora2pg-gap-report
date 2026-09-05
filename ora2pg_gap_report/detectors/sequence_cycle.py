import re

from .. import plsql_lex
from ..plsql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, STATEMENT_CLAUSE, build

_SEQUENCE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+SEQUENCE"),
    re.IGNORECASE,
)
# 'NOCYCLE' does NOT match here: \b requires a non-word boundary, and 'O'
# immediately preceding 'CYCLE' in 'NOCYCLE' is itself a word character,
# so there's no boundary between them -- no separate negative lookbehind
# needed (same reasoning as read_only_table.py's word-boundary handling
# of a literally-named column).
_CYCLE_RE = re.compile(r"\bCYCLE\b", re.IGNORECASE)

_DOC = """Detect Oracle's CREATE SEQUENCE ... CYCLE. ora2pg drops the CYCLE
clause entirely, so the generated sequence raises an error once its
range is exhausted instead of wrapping around -- not a syntax error,
a silent loss of behavior that only surfaces once the sequence's
range is actually exhausted (potentially long after migration). See
docs/research/gap-030-sequence-cycle.md.

object_name is the sequence's own name (schema-level DDL) -- same
reasoning as read_only_table.py for skipping enclosing_object_name().
Statement scoping uses statement_end(), same as read_only_table.py."""

SPEC = DetectorSpec(
    name="sequence_cycle",
    dialect="oracle",
    severity="high",
    pattern=_CYCLE_RE,
    strategy=STATEMENT_CLAUSE,
    snippet='CYCLE',
    statement_pattern=_SEQUENCE_RE,
)

find_sequence_cycle_usage = build(SPEC, plsql_lex)
find_sequence_cycle_usage.__doc__ = _DOC
