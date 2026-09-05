import re

from .. import plsql_lex
from ..plsql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, STATEMENT_CLAUSE, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# Excludes a double-quoted column literally named "READ ONLY" (a valid
# Oracle identifier) -- mask_strings_and_comments() only masks
# single-quoted string literals/comments, never double-quoted identifiers,
# so the literal text survives with its quotes intact right up against
# the words.
_READ_ONLY_RE = re.compile(r'(?<!")\bREAD\s+ONLY\b(?!")', re.IGNORECASE)

_DOC = """Detect Oracle's CREATE TABLE ... READ ONLY. ora2pg drops the
clause entirely, so the table becomes an ordinary writable one --
not a syntax error, but a silent loss of a server-enforced integrity
guarantee (Oracle would reject any DML against it with ORA-12081).
See docs/research/gap-026-read-only-table.md.

object_name is the table's own name (schema-level DDL) -- same
reasoning as table_partitioning.py/external_table.py for skipping
enclosing_object_name().

Statement scoping uses statement_end() -- up to the next ';', or the
start of the next CREATE TABLE if there's no ';' (DBMS_METADATA.GET_DDL's
default output has none) -- not just "next ';' or end of file", which
would otherwise misattribute a later table's own READ ONLY clause to
an earlier, unterminated one. The reported line is the actual READ
ONLY token's line, not the statement's opening CREATE TABLE line --
real tables are often multi-line, and pointing at the wrong line
sends the reader to the wrong place in the file."""

SPEC = DetectorSpec(
    name="read_only_table",
    dialect="oracle",
    severity="high",
    pattern=_READ_ONLY_RE,
    strategy=STATEMENT_CLAUSE,
    snippet='READ ONLY',
    statement_pattern=_TABLE_RE,
)

find_read_only_tables = build(SPEC, plsql_lex)
find_read_only_tables.__doc__ = _DOC
