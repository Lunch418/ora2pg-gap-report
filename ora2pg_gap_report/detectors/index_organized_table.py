import re

from .. import plsql_lex
from ..plsql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, STATEMENT_CLAUSE, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# Excludes a double-quoted column literally named "ORGANIZATION INDEX" (a
# valid Oracle identifier) -- mask_strings_and_comments() only masks
# single-quoted string literals/comments, never double-quoted identifiers,
# so the literal text survives with its quotes intact right up against
# the words. Same guard as read_only_table.py's own READ ONLY regex.
_ORGANIZATION_INDEX_RE = re.compile(r'(?<!")\bORGANIZATION\s+INDEX\b(?!")', re.IGNORECASE)

_DOC = """Detect Oracle's CREATE TABLE ... ORGANIZATION INDEX. ora2pg drops
the ORGANIZATION INDEX clause entirely, so the table converts as an
ordinary heap table with a separate primary-key index -- correct
with respect to integrity constraints, but not the same storage
architecture (PostgreSQL has no true index-organized table where
data lives physically inside the index structure). Not a
correctness break -- a medium-severity architectural/performance
concern for storage-sensitive lookup tables originally designed as
an IOT for exactly that property. See
docs/research/gap-037-index-organized-table.md.

object_name is the table's own name (schema-level DDL) -- same
reasoning as read_only_table.py for skipping enclosing_object_name().
Statement scoping uses statement_end(), same as read_only_table.py."""

SPEC = DetectorSpec(
    name="index_organized_table",
    dialect="oracle",
    severity="medium",
    pattern=_ORGANIZATION_INDEX_RE,
    strategy=STATEMENT_CLAUSE,
    snippet='ORGANIZATION INDEX',
    statement_pattern=_TABLE_RE,
)

find_index_organized_tables = build(SPEC, plsql_lex)
find_index_organized_tables.__doc__ = _DOC
