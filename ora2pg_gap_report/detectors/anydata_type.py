import re

from .. import plsql_lex
from ..plsql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# ANYDATA / ANYDATASET / ANYTYPE, with or without the SYS. prefix -- all
# three are the same self-describing-container family and ora2pg treats
# them the same way (it passes the type name straight through).
_ANYDATA_RE = re.compile(
    r"\b(?:SYS\s*\.\s*)?(ANYDATASET|ANYDATA|ANYTYPE)\b",
    re.IGNORECASE,
)

_DOC = """Detect Oracle ANYDATA/ANYDATASET/ANYTYPE columns. ora2pg copies
the type name through unchanged and PostgreSQL has neither the type
nor the SYS schema, so the generated DDL fails to load. See
docs/research/gap-051-anydata-type.md."""

SPEC = DetectorSpec(
    name="anydata_type",
    dialect="oracle",
    severity="high",
    pattern=_ANYDATA_RE,
    strategy=TABLE_COLUMNS,
    snippet=lambda m: m.group(1).upper(),
    table_pattern=_TABLE_RE,
)

find_anydata_columns = build(SPEC, plsql_lex)
find_anydata_columns.__doc__ = _DOC
