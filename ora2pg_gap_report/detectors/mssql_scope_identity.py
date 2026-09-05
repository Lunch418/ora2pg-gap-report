import re

from .. import mssql_lex
from ..detector_spec import DetectorSpec, build

# '@@IDENTITY' cannot use a leading \b: '@' is not a word character, so
# there is no boundary between it and the preceding space. Matched as its
# own alternative instead.
_PATTERN_RE = re.compile(r"(?:\b(SCOPE_IDENTITY|IDENT_CURRENT)\b|(@@IDENTITY)\b)", re.IGNORECASE)

_DOC = """Detect SCOPE_IDENTITY()/@@IDENTITY/IDENT_CURRENT(). ora2pg -M
copies them through unchanged and PostgreSQL has no such function or
system variable, so the containing routine loads cleanly and fails on
its first call. See docs/research/gap-096-mssql-scope-identity.md."""

SPEC = DetectorSpec(
    name="mssql_scope_identity",
    dialect="mssql",
    severity="high",
    pattern=_PATTERN_RE,
    snippet=lambda m: (m.group(1) or m.group(2)).upper(),
)

find_mssql_scope_identity = build(SPEC, mssql_lex)
find_mssql_scope_identity.__doc__ = _DOC
