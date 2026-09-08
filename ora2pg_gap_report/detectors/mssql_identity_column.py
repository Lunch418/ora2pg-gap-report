import re

from .. import mssql_lex
from ..mssql_lex import normalize_name, qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# \b after IDENTITY (not just before) so a column name that merely starts
# with the word -- IDENTITY_FLAG, say -- doesn't match: the original
# pattern had no right-side boundary, so "IDENTITY_FLAG bit" matched
# "IDENTITY" as if the column itself had the property.
_PATTERN_RE = re.compile(r"\bIDENTITY\b\s*(?:\(\s*\d+\s*,\s*\d+\s*\))?", re.IGNORECASE)

_DOC = """Detect T-SQL IDENTITY columns. On the file-based path this
project scans, ora2pg -M drops the property entirely -- the column
becomes a plain integer with no serial, no GENERATED clause and no
sequence anywhere in the output -- so an INSERT that relied on the
server supplying the key fails on the NOT NULL constraint. MSSQL.pm's
_get_identities() only ever queries sys.identity_columns over a live
connection, with no DDL-text fallback for IDENTITY(seed, increment);
unlike mssql_foreign_key, this one is unaffected by PG_VERSION and is
genuinely specific to the file-based path.
See docs/research/gap-090-mssql-identity-column.md."""

SPEC = DetectorSpec(
    name="mssql_identity_column",
    dialect="mssql",
    severity="high",
    pattern=_PATTERN_RE,
    strategy=TABLE_COLUMNS,
    snippet='IDENTITY',
    statement_pattern=_TABLE_RE,
    normalize_object_name=normalize_name,
)

find_mssql_identity_columns = build(SPEC, mssql_lex)
find_mssql_identity_columns.__doc__ = _DOC
