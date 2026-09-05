import re

from .. import plsql_lex
from ..plsql_lex import IDENTIFIER
from ..detector_spec import DetectorSpec, MATCH_NAMED, build

# CREATE [UNIQUE] BITMAP INDEX <name> -- captures the index's own name for
# attribution. BITMAP JOIN INDEX (a separate Oracle feature built on the
# same keyword) is matched too: it converts the same way and breaks the
# same way, and the alternative -- silently ignoring it -- would be the
# worse failure mode.
_BITMAP_INDEX_RE = re.compile(
    rf"\bCREATE\s+BITMAP\s+(?:JOIN\s+)?INDEX\s+({IDENTIFIER}(?:\s*\.\s*{IDENTIFIER})?)",
    re.IGNORECASE,
)


def _without_spaces(name: str) -> str:
    """A qualified name with the whitespace around its dot removed, so
    `SCHEMA . IDX` and `SCHEMA.IDX` are reported as one object rather
    than two."""
    return re.sub(r"\s+", "", name)


_DOC = """Detect Oracle's CREATE BITMAP INDEX. ora2pg rewrites it to a GIN
index, which PostgreSQL refuses to create on an ordinary scalar
column -- GIN has no default operator class for varchar or numeric --
so the generated DDL fails at load time. See
docs/research/gap-046-bitmap-index.md.

object_name is the index's own name: this is standalone schema-level
DDL, not a clause inside a CREATE TABLE, so there's no enclosing
table to attribute it to (the target table is in the ON clause, but
the failing object is the index itself)."""

SPEC = DetectorSpec(
    name="bitmap_index",
    dialect="oracle",
    severity="high",
    pattern=_BITMAP_INDEX_RE,
    strategy=MATCH_NAMED,
    snippet="CREATE BITMAP INDEX",
    normalize_object_name=_without_spaces,
)

find_bitmap_indexes = build(SPEC, plsql_lex)
find_bitmap_indexes.__doc__ = _DOC
