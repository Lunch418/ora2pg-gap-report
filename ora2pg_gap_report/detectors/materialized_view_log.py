import re

from .. import plsql_lex
from ..plsql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, MATCH_NAMED, build

_MVIEW_LOG_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+MATERIALIZED\s+VIEW\s+LOG\s+ON"),
    re.IGNORECASE,
)

_DOC = """Detect Oracle's CREATE MATERIALIZED VIEW LOG ON <table>. ora2pg has
no conversion path for these at all -- see
docs/research/gap-027-materialized-view-log.md.

object_name is the target table's name (schema-level DDL) -- same
reasoning as table_partitioning.py/external_table.py for skipping
enclosing_object_name()."""

SPEC = DetectorSpec(
    name="materialized_view_log",
    dialect="oracle",
    severity="high",
    pattern=_MVIEW_LOG_RE,
    strategy=MATCH_NAMED,
    snippet='CREATE MATERIALIZED VIEW LOG',
)

find_materialized_view_logs = build(SPEC, plsql_lex)
find_materialized_view_logs.__doc__ = _DOC
