import re

from .. import plsql_lex
from ..plsql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, TABLE_COLUMNS, build

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# TIMESTAMP [(p)] WITH LOCAL TIME ZONE, specifically -- plain
# `TIMESTAMP WITH TIME ZONE` (no LOCAL) is a different Oracle type that
# ora2pg maps correctly onto PostgreSQL's timestamptz, and must not be
# flagged. The optional precision is part of the match but isn't captured
# separately: the finding is about the type's time-zone semantics, not
# its fractional-second precision.
_LTZ_COLUMN_RE = re.compile(
    r"\bTIMESTAMP\b(?:\s*\(\s*\d+\s*\))?\s+WITH\s+LOCAL\s+TIME\s+ZONE\b",
    re.IGNORECASE,
)

_DOC = """Detect Oracle's TIMESTAMP WITH LOCAL TIME ZONE used as a column
type. ora2pg converts it to a plain `timestamp` (no time zone at
all), silently dropping the session-time-zone normalisation that is
the entire point of the Oracle type -- PostgreSQL's `timestamptz`
would be the faithful target. No error is ever raised. See
docs/research/gap-044-local-time-zone.md.

object_name is the table's own name (schema-level DDL) -- same
reasoning as rowid_type.py, whose column-list scoping this mirrors:
only the '(...)' column-definition list right after the table name is
searched, so a trailing AS SELECT clause can't be misread as a type
declaration."""

SPEC = DetectorSpec(
    name="local_time_zone",
    dialect="oracle",
    severity="high",
    pattern=_LTZ_COLUMN_RE,
    strategy=TABLE_COLUMNS,
    snippet=lambda m: re.sub(r"\s+", " ", m.group(0).strip().upper()),
    statement_pattern=_TABLE_RE,
)

find_local_time_zone_columns = build(SPEC, plsql_lex)
find_local_time_zone_columns.__doc__ = _DOC
