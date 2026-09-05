import re

from .. import plsql_lex
from ..plsql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# Oracle's virtual-column grammar is 'column [datatype] [GENERATED
# ALWAYS] AS (expression) [VIRTUAL]' -- both the GENERATED ALWAYS prefix
# and the trailing VIRTUAL keyword are optional (confirmed against real
# ora2pg: 'c NUMBER GENERATED ALWAYS AS (a+b)' with no VIRTUAL, and the
# shortest form 'total_value AS (item_id * quantity + net_value)' with
# neither, both convert identically to the same trigger-based emulation
# and lose the same ORA-54016 protection as the full form -- see
# docs/research/gap-033-virtual-column.md). So this matches on the bare
# 'AS (' that's common to all three forms, not on GENERATED ALWAYS or
# VIRTUAL. This deliberately does NOT collide with GAP-028's identity
# columns: an identity column's syntax is 'GENERATED ALWAYS AS IDENTITY
# (...)' -- IDENTITY is a bare keyword directly after AS, not '(', so
# 'AS\s*\(' never matches at that position in the first place.
_AS_EXPR_OPEN_RE = re.compile(r"\bAS\s*\(", re.IGNORECASE)

_DOC = """Detect Oracle's virtual-column clause -- 'column [datatype]
[GENERATED ALWAYS] AS (expression) [VIRTUAL]', in any of its three
valid forms (GENERATED ALWAYS and VIRTUAL are each independently
optional in Oracle's own grammar). ora2pg converts the computation
correctly for all three (as a BEFORE INSERT OR UPDATE trigger rather
than PostgreSQL's native GENERATED ALWAYS AS (...) STORED), but
loses Oracle's server-level protection against explicitly assigning
a value to the column (ORA-54016) -- the generated trigger silently
overwrites whatever value was explicitly given, with no error. See
docs/research/gap-033-virtual-column.md.

object_name is the table's own name (schema-level DDL) -- same
reasoning as read_only_table.py for skipping enclosing_object_name().

Scoped to just the '(...)' column-definition list right after the
table name (table_column_definition_list()), same as rowid_type.py
-- a virtual column clause only makes sense there, and this keeps a
bare CTAS (no column-type list at all) out of scope the same way."""

SPEC = DetectorSpec(
    name="virtual_column",
    dialect="oracle",
    severity="medium",
    pattern=_AS_EXPR_OPEN_RE,
    strategy=TABLE_COLUMNS,
    snippet='AS (...)',
    statement_pattern=_TABLE_RE,
)

find_virtual_columns = build(SPEC, plsql_lex)
find_virtual_columns.__doc__ = _DOC
