import re

from .. import plsql_lex
from ..plsql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, STATEMENT_CLAUSE, build

_INDEX_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+(?:UNIQUE\s+|BITMAP\s+)?INDEX"),
    re.IGNORECASE,
)
# Excludes two collision shapes where "invisible" is actually a column
# name being indexed, not the trailing INVISIBLE modifier: (1) unquoted,
# e.g. 'ON widgets(invisible, other_col)' -- always immediately followed
# by ',' or ')' there, never by the real modifier; (2) double-quoted,
# e.g. 'ON widgets("invisible")' -- mask_strings_and_comments() only masks
# single-quoted string literals/comments, never double-quoted identifiers,
# so the literal text survives with its quotes intact.
_INVISIBLE_RE = re.compile(r'(?<!")\bINVISIBLE\b(?!")(?!\s*[,)])', re.IGNORECASE)

_DOC = """Detect Oracle's INVISIBLE index modifier. ora2pg drops it entirely,
so the index becomes an ordinary visible one -- not a syntax error,
but a silent behavior change: the optimizer starts considering an
index Oracle would have hidden by default. See
docs/research/gap-025-invisible-index.md.

object_name is the index's own name (schema-level DDL) -- same
reasoning as table_partitioning.py/external_table.py for skipping
enclosing_object_name().

Statement scoping uses statement_end() -- up to the next ';', or the
start of the next CREATE INDEX if there's no ';' (DBMS_METADATA.GET_DDL's
default output has none) -- not just "next ';' or end of file", which
would otherwise misattribute a later index's own INVISIBLE modifier
to an earlier, unterminated one. The reported line is the actual
INVISIBLE token's line, not the statement's opening CREATE INDEX
line -- real indexes are often multi-line, and pointing at the wrong
line sends the reader to the wrong place in the file."""

SPEC = DetectorSpec(
    name="invisible_index",
    dialect="oracle",
    severity="medium",
    pattern=_INVISIBLE_RE,
    strategy=STATEMENT_CLAUSE,
    snippet='INVISIBLE',
    statement_pattern=_INDEX_RE,
)

find_invisible_indexes = build(SPEC, plsql_lex)
find_invisible_indexes.__doc__ = _DOC
