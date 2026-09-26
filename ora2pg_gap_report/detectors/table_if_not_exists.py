import re

from .. import plsql_lex
from ..plsql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, MATCH_NAMED, build

_IF_NOT_EXISTS_TABLE_RE = re.compile(
    qualified_name_pattern(r"\bCREATE\s+TABLE\s+IF\s+NOT\s+EXISTS"),
    re.IGNORECASE,
)

_DOC = """Detect Oracle 23ai's CREATE TABLE IF NOT EXISTS. ora2pg takes the
word after TABLE as the table's name, so the table comes out as
`CREATE TABLE if ( not EXISTS ...` with its real name and columns lost,
and PostgreSQL rejects it with 'syntax error at or near "not"' --
stopping the whole schema load under the file's `\\set ON_ERROR_STOP
ON`. The same table without IF NOT EXISTS converts. DBMS_METADATA.GET_DDL
never writes the clause; hand-maintained 23ai scripts do. See
docs/research/gap-112-table-if-not-exists.md."""

SPEC = DetectorSpec(
    name="table_if_not_exists",
    dialect="oracle",
    severity="high",
    pattern=_IF_NOT_EXISTS_TABLE_RE,
    strategy=MATCH_NAMED,
    snippet="CREATE TABLE IF NOT EXISTS",
)

find_table_if_not_exists = build(SPEC, plsql_lex)
find_table_if_not_exists.__doc__ = _DOC
