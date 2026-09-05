import re

from .. import mssql_lex
from ..mssql_lex import normalize_name, qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
_PATTERN_RE = re.compile(r"\b(?:NEWID|NEWSEQUENTIALID)\s*\(\s*\)", re.IGNORECASE)

_DOC = """Detect NEWID()/NEWSEQUENTIALID() column defaults. ora2pg -M
maps them onto uuid_generate_v4() but never emits the CREATE
EXTENSION "uuid-ossp" that function needs, so the generated CREATE
TABLE fails to load. See docs/research/gap-088-mssql-newid-default.md."""

SPEC = DetectorSpec(
    name="mssql_newid_default",
    dialect="mssql",
    severity="high",
    pattern=_PATTERN_RE,
    strategy=TABLE_COLUMNS,
    snippet=lambda m: m.group(0).upper(),
    table_pattern=_TABLE_RE,
    normalize_table_name=normalize_name,
)

find_mssql_newid_defaults = build(SPEC, mssql_lex)
find_mssql_newid_defaults.__doc__ = _DOC
