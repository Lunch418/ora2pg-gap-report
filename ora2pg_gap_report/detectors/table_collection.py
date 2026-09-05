import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, MASK_DYNAMIC_SQL_VISIBLE, build

# The TABLE(...) collection-unnesting operator, which only ever appears in
# a FROM clause (or after a join keyword). Anchoring on the preceding
# FROM/JOIN keyword is what keeps `CREATE TABLE (`, `ALTER TABLE ... (`,
# `TRUNCATE TABLE ...`, `TYPE t IS TABLE OF ...` and every other ordinary
# use of the word TABLE out of the results -- the bare word is far too
# common in SQL to match on its own.
_TABLE_OPERATOR_RE = re.compile(
    r"\b(?:FROM|JOIN|CROSS\s+APPLY|OUTER\s+APPLY)\s*,?\s*(?:THE\s+)?TABLE\s*\(",
    re.IGNORECASE,
)

_DOC = """Detect Oracle's TABLE(...) collection-unnesting operator in a FROM
clause. ora2pg copies it through unchanged; PostgreSQL has no such
operator, so the generated query fails to parse. See
docs/research/gap-054-table-collection.md."""

SPEC = DetectorSpec(
    name="table_collection",
    dialect="oracle",
    severity="high",
    pattern=_TABLE_OPERATOR_RE,
    snippet='TABLE(',
    search_mask=MASK_DYNAMIC_SQL_VISIBLE,
)

find_table_collection_operator = build(SPEC, plsql_lex)
find_table_collection_operator.__doc__ = _DOC
