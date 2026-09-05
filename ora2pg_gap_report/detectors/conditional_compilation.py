import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, build

# Oracle's PL/SQL conditional-compilation preprocessor directives. '$IF',
# '$ELSIF', '$ELSE', '$END' are the ones that actually gate whether code
# compiles at all -- '$$identifier' (an inquiry directive, e.g.
# '$$debug_mode') on its own, without a controlling $IF, is comparatively
# harmless (just a compile-time constant substitution), so this
# deliberately only fires on the directive keywords themselves.
_COND_COMPILE_RE = re.compile(r"\$(IF|ELSIF|ELSE|END)\b", re.IGNORECASE)

_DOC = """Detect Oracle's PL/SQL conditional-compilation directives ($IF/
$ELSIF/$ELSE/$END). ora2pg copies them into the generated PL/pgSQL
body verbatim as plain text -- PostgreSQL has no such preprocessor
at all, so this is a syntax error at the first real call, not at
CREATE time (ora2pg disables check_function_bodies in its own
output). See docs/research/gap-035-conditional-compilation.md."""

SPEC = DetectorSpec(
    name="conditional_compilation",
    dialect="oracle",
    severity="high",
    pattern=_COND_COMPILE_RE,
    snippet=lambda m: m.group(0),
)

find_conditional_compilation = build(SPEC, plsql_lex)
find_conditional_compilation.__doc__ = _DOC
