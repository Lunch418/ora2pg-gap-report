import re

from .. import mysql_lex
from ..detector_spec import DetectorSpec, build

_SIGNAL_RE = re.compile(r"\b(SIGNAL|RESIGNAL)\b", re.IGNORECASE)

_DOC = """Detect MySQL/MariaDB's SIGNAL and RESIGNAL statements. ora2pg -m
copies them through unchanged and PL/pgSQL has no such statement at
all, so the containing procedure/function loads cleanly (bodies are
not checked) and then fails on its first call. See docs/research/
gap-071-mysql-signal.md."""

SPEC = DetectorSpec(
    name="mysql_signal",
    dialect="mysql",
    severity="high",
    pattern=_SIGNAL_RE,
    snippet=lambda m: m.group(1).upper(),
)

find_mysql_signal_statements = build(SPEC, mysql_lex)
find_mysql_signal_statements.__doc__ = _DOC
