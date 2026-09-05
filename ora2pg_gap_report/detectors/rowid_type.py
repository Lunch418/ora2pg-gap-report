import re

from .. import plsql_lex
from ..plsql_lex import IDENTIFIER, qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# A column's own data type, not the ROWID/UROWID pseudocolumn used in a
# SELECT ('SELECT ROWID FROM ...', a common idiom in CREATE TABLE ... AS
# SELECT ROWID rid, ...). Requiring a preceding identifier alone doesn't
# rule that out -- 'SELECT' is itself a preceding identifier -- so this
# is only searched against the column-definition list's own text (see
# find_rowid_types()), never a CTAS's trailing AS SELECT clause. The
# lookbehind (not \b) allows an optional double-quoted column name
# ('"ROW_REF" rowid') -- \b would fail right at a leading '"', since
# neither the quote nor typical preceding whitespace/comma is a word
# character, so there'd be no boundary transition to match on. Not
# verifying a leading quote is matched by a trailing one, same
# deliberate simplification as qualified_name_pattern()'s own docstring.
# UROWID's optional size, e.g. 'UROWID(4000)', is part of the match but
# not captured separately -- the finding is about the type itself, not
# its size.
_ROWID_COLUMN_RE = re.compile(
    rf'(?<![A-Za-z0-9_$#])"?({IDENTIFIER})"?\s+(ROWID|UROWID)\b(?:\s*\(\s*\d+\s*\))?',
    re.IGNORECASE,
)

_DOC = """Detect Oracle's ROWID/UROWID used as a column's data type. ora2pg
converts it to `oid`, PostgreSQL's own internal object-identifier
type -- a real datatype, not a fallback text/blob, so CREATE TABLE
succeeds -- but any actual Oracle ROWID value fails INSERT into it,
since Oracle ROWID's string representation isn't valid oid input.
See docs/research/gap-029-rowid-urowid.md.

object_name is the table's own name (schema-level DDL) -- same
reasoning as read_only_table.py for skipping enclosing_object_name().

Deliberately scoped to just the '(...)' column-definition list right
after the table name, not the whole statement up to the next ';' the
way read_only_table.py/default_on_null.py are: a CREATE TABLE ... AS
SELECT ROWID rid, ... (a common dedup/diagnostic-table idiom) has no
column-type list at all -- ROWID there is the pseudocolumn in the
SELECT, not a type declaration -- and searching past the column list
into that trailing clause would misdetect it as one. A CREATE TABLE
with no '(' immediately following the name (a bare CTAS) is skipped
entirely -- nothing case."""

SPEC = DetectorSpec(
    name="rowid_type",
    dialect="oracle",
    severity="high",
    pattern=_ROWID_COLUMN_RE,
    strategy=TABLE_COLUMNS,
    snippet=lambda m: re.sub(r"\s+", " ", m.group(0).strip()),
    table_pattern=_TABLE_RE,
)

find_rowid_types = build(SPEC, plsql_lex)
find_rowid_types.__doc__ = _DOC
