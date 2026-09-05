import re

from .. import plsql_lex
from ..plsql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, MATCH_NAMED, build

_CREATE_TYPE_PREFIX = r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:EDITIONABLE\s+|NONEDITIONABLE\s+)?TYPE"
# VARYING ARRAY is Oracle's documented synonym for VARRAY in this clause
# (collection_type_definition: '{VARRAY | VARYING ARRAY} (size) OF ...').
_COLLECTION_TYPE_RE = re.compile(
    qualified_name_pattern(_CREATE_TYPE_PREFIX)
    + r"\s+(?:IS|AS)\s+(?:TABLE\s+OF\b|(?:VARRAY|VARYING\s+ARRAY)\s*\(\s*\d+\s*\)\s*OF\b)",
    re.IGNORECASE,
)

_DOC = """Detect Oracle collection type declarations (CREATE TYPE ... AS/IS
TABLE OF / VARRAY(n) OF). Unlike object types (object_type.py /
GAP-009), which ora2pg at least copies through with an explicit
'Unsupported' marker, collection types vanish from the output
entirely with no marker at all -- only a DEBUG-level log line. Any
table using the type as a column type then fails outright on DDL
load, since the type was never created. See
docs/research/gap-021-collection-type.md.

object_name is the type's own name (declared at schema level, never
nested inside a package/routine) -- same reasoning as object_type.py
for skipping enclosing_object_name()."""

SPEC = DetectorSpec(
    name="collection_type",
    dialect="oracle",
    severity="high",
    pattern=_COLLECTION_TYPE_RE,
    strategy=MATCH_NAMED,
    snippet='CREATE TYPE ... TABLE OF / VARRAY OF',
)

find_collection_types = build(SPEC, plsql_lex)
find_collection_types.__doc__ = _DOC
