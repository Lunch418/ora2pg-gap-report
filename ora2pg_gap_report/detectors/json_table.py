import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

_JSON_TABLE_RE = re.compile(r"\bJSON_TABLE\s*\(", re.IGNORECASE)

_DOC = """Detect Oracle's JSON_TABLE(...) SQL/JSON function. ora2pg passes it
through unchanged; PostgreSQL 16 and earlier have no such function at
all (PostgreSQL 17 added JSON_TABLE, but with a COLUMNS syntax not
verified here to match Oracle's own). See
docs/research/gap-017-json-table.md."""

SPEC = DetectorSpec(
    name="json_table",
    dialect="oracle",
    severity="high",
    pattern=_JSON_TABLE_RE,
    snippet='JSON_TABLE(...)',
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_json_table_calls = build(SPEC, plsql_lex)
find_json_table_calls.__doc__ = _DOC
