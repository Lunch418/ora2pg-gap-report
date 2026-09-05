import re

from .. import mssql_lex
from ..detector_spec import DetectorSpec, build

_PATTERN_RE = re.compile(r"\b(RAISERROR|THROW)\b", re.IGNORECASE)

_DOC = """Detect T-SQL RAISERROR and THROW. ora2pg -M copies both through
unchanged; PL/pgSQL has neither, so the containing routine loads
cleanly and fails on its first call. See docs/research/
gap-093-mssql-raiserror.md."""

SPEC = DetectorSpec(
    name="mssql_raiserror",
    dialect="mssql",
    severity="high",
    pattern=_PATTERN_RE,
    snippet=lambda m: m.group(1).upper(),
)

find_mssql_raiserror = build(SPEC, mssql_lex)
find_mssql_raiserror.__doc__ = _DOC
