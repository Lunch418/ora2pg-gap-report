import re

from .. import mssql_lex
from ..mssql_lex import normalize_name
from ..detector_spec import DetectorSpec, MATCH_NAMED, build

# A CREATE statement whose object name (or its schema qualifier) is
# bracket-delimited. Deliberately anchored to the CREATE, not to every
# bracket in the file: SSMS brackets *every* identifier, so flagging each
# occurrence would bury a 200-line script under 200 identical findings
# when the actionable unit is "this object will not convert". The name
# is captured with its delimiters and cleaned by normalize_name().
_BRACKETED_CREATE_RE = re.compile(
    r"\bCREATE\s+(?:OR\s+ALTER\s+)?"
    r"(?:UNIQUE\s+|CLUSTERED\s+|NONCLUSTERED\s+)*"
    r"(TABLE|PROC(?:EDURE)?|FUNCTION|VIEW|TRIGGER|INDEX)\s+"
    r"(?:\[[^\]]*\]\s*\.\s*)*"  # optional bracketed db/schema qualifiers
    r"(\[[^\]]*\])",  # the object's own bracketed name
    re.IGNORECASE,
)

_DOC = """Detect bracket-delimited identifiers on T-SQL CREATE statements.
ora2pg -M's file-based path never strips them -- the brackets end up
inside the generated identifier, and inside type names -- so the DDL
fails to load. One finding per CREATE, not per bracket. See
docs/research/gap-087-mssql-bracket-identifier.md."""

SPEC = DetectorSpec(
    name="mssql_bracket_identifier",
    dialect="mssql",
    severity="high",
    pattern=_BRACKETED_CREATE_RE,
    strategy=MATCH_NAMED,
    snippet=lambda m: f"CREATE {m.group(1).upper()} {m.group(2)}",
    normalize_object_name=normalize_name,
    name_group=2,
)

find_mssql_bracket_identifiers = build(SPEC, mssql_lex)
find_mssql_bracket_identifiers.__doc__ = _DOC
