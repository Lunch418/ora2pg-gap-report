import re

from .. import mssql_lex
from ..detector_spec import DetectorSpec, build

# Any T-SQL IF: both shapes below are broken, differently, so the
# detector deliberately doesn't try to tell them apart. The negative
# lookahead excludes IF EXISTS/IF NOT EXISTS -- not the conditional this
# detector is about, but the idempotent-DDL idiom `DROP TABLE IF EXISTS
# ...` (also PROCEDURE/VIEW/INDEX), which is neither broken by ora2pg nor
# a statement at all, and without it every DROP ... IF EXISTS line in an
# ordinary idempotent SSMS script was reported as a high-severity finding.
# Trade-off: a genuine `IF EXISTS(...) BEGIN ... END` conditional (which
# ora2pg mishandles exactly like any other IF) stops being flagged too --
# there is no regex-only way to tell the two apart, and silence here is
# the safer failure mode than flooding every idempotent script with noise.
_PATTERN_RE = re.compile(r"\bIF\b(?!\s+(?:NOT\s+)?EXISTS\b)\s+", re.IGNORECASE)

_DOC = """Detect T-SQL IF statements. ora2pg -M mishandles both shapes:
with a BEGIN/END block it adds THEN but never closes with END IF,
and without a block it adds no THEN at all. Either way the routine
loads cleanly and fails on its first call. See docs/research/
gap-092-mssql-if-statement.md."""

SPEC = DetectorSpec(
    name="mssql_if_statement",
    dialect="mssql",
    severity="high",
    pattern=_PATTERN_RE,
    snippet='IF',
)

find_mssql_if_statements = build(SPEC, mssql_lex)
find_mssql_if_statements.__doc__ = _DOC
