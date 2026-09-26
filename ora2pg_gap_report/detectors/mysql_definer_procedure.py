import re

from .. import mysql_lex
from ..mysql_lex import qualified_name_pattern
from ..detector_spec import DetectorSpec, MATCH_NAMED, build

# A procedure (not a function) with a DEFINER clause -- the way mysqldump
# writes every procedure. DEFINER's value is matched up to the whitespace
# before PROCEDURE without crossing a ';' (see mysql_lex._CREATE_PREFIX
# for why: a quoted 'user'@'host' is blanks in the masked text).
_DEFINER_PROCEDURE_RE = re.compile(
    qualified_name_pattern(
        r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:ALGORITHM\s*=\s*\w+\s+)?DEFINER\s*=[^;]*?\s+"
        r"(?:SQL\s+SECURITY\s+\w+\s+)?PROCEDURE(?:\s+IF\s+NOT\s+EXISTS)?"
    ),
    re.IGNORECASE,
)

_DOC = """Detect a MySQL/MariaDB procedure declared with DEFINER=..., which
is how mysqldump writes every procedure. ora2pg -m -t PROCEDURE never
exports one: export_procedure()'s line parser, unlike export_function()'s,
has no DEFINER= alternative in its CREATE patterns, so the procedure's
name is never picked up and its text is skipped without a word. The
same procedure without DEFINER is exported, and -t FUNCTION -- whose
parser does handle DEFINER -- exports it too, which is the way around
it. See docs/research/gap-108-mysql-definer-procedure.md."""

SPEC = DetectorSpec(
    name="mysql_definer_procedure",
    dialect="mysql",
    severity="high",
    pattern=_DEFINER_PROCEDURE_RE,
    strategy=MATCH_NAMED,
    snippet="CREATE DEFINER=... PROCEDURE",
)

find_mysql_definer_procedures = build(SPEC, mysql_lex)
find_mysql_definer_procedures.__doc__ = _DOC
