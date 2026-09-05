import re

from .. import plsql_lex
from ..plsql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_STATEMENT, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# Oracle's actual grammar is 'DEFAULT [ON NULL] expr' -- ON NULL directly
# follows the DEFAULT keyword, *before* the expression, not after it
# (easy to get backwards; confirmed against the real syntax and against
# what ora2pg actually accepted as input, docs/research/gap-031-default-
# on-null.md). No expression can appear between DEFAULT and ON NULL, so
# there's no comma-bridging risk to guard against here, unlike a regex
# that had to search past an arbitrary expression.
_DEFAULT_ON_NULL_RE = re.compile(r"\bDEFAULT\s+ON\s+NULL\b", re.IGNORECASE)

_DOC = """Detect Oracle 12c+'s DEFAULT ON NULL <expr> column clause. ora2pg
copies the ON NULL section into the generated CREATE TABLE verbatim
-- PostgreSQL has no such DEFAULT variant at all, so this is a hard
syntax error at DDL-apply time itself, not a later runtime surprise
like most other gaps in this registry. See
docs/research/gap-031-default-on-null.md.

object_name is the table's own name (schema-level DDL) -- same
reasoning as read_only_table.py for skipping enclosing_object_name().
Statement scoping uses statement_end(), same as read_only_table.py."""

SPEC = DetectorSpec(
    name="default_on_null",
    dialect="oracle",
    severity="high",
    pattern=_DEFAULT_ON_NULL_RE,
    strategy=TABLE_STATEMENT,
    snippet=lambda m: re.sub(r"\s+", " ", m.group(0).strip()),
    table_pattern=_TABLE_RE,
)

find_default_on_null_usage = build(SPEC, plsql_lex)
find_default_on_null_usage.__doc__ = _DOC
