import re

from .. import plsql_lex
from ..plsql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# LONG RAW specifically -- plain LONG is Oracle's legacy *character* type
# and `LONG:text` is both ora2pg's documented mapping and the right one,
# so it must not be flagged. Only the binary variant is converted against
# ora2pg's own documented default.
_LONG_RAW_RE = re.compile(r"\bLONG\s+RAW\b", re.IGNORECASE)

_DOC = """Detect Oracle LONG RAW columns. ora2pg maps them to `text` even
though its own documented default is `LONG RAW:bytea`, so binary
content cannot be loaded into the generated column. See
docs/research/gap-050-long-raw-type.md."""

SPEC = DetectorSpec(
    name="long_raw_type",
    dialect="oracle",
    severity="high",
    pattern=_LONG_RAW_RE,
    strategy=TABLE_COLUMNS,
    snippet='LONG RAW',
    statement_pattern=_TABLE_RE,
)

find_long_raw_columns = build(SPEC, plsql_lex)
find_long_raw_columns.__doc__ = _DOC
