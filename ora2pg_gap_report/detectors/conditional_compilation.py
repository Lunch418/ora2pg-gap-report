import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

# Oracle's PL/SQL conditional-compilation preprocessor directives. '$IF',
# '$ELSIF', '$ELSE', '$END' are the ones that actually gate whether code
# compiles at all -- '$$identifier' (an inquiry directive, e.g.
# '$$debug_mode') on its own, without a controlling $IF, is comparatively
# harmless (just a compile-time constant substitution), so this
# deliberately only fires on the directive keywords themselves.
_COND_COMPILE_RE = re.compile(r"\$(IF|ELSIF|ELSE|END)\b", re.IGNORECASE)

_MESSAGE = (
    "Директивы условной компиляции PL/SQL ($IF/$ELSIF/$ELSE/$END) — "
    "препроцессор, обрабатываемый компилятором Oracle до собственно "
    "компиляции тела: код в невыбранной ветке не просто пропускается на "
    "выполнении, он вообще не компилируется. ora2pg копирует директивы в "
    "вывод буквально, как обычный текст (подтверждено реальным прогоном "
    "ora2pg + PostgreSQL 16, "
    "docs/research/gap-035-conditional-compilation.md) — у PL/pgSQL нет "
    "препроцессора условной компиляции вообще, это не валидный синтаксис "
    "ни в каком виде. CREATE PROCEDURE/FUNCTION проходит без единой "
    "ошибки (ora2pg отключает check_function_bodies в своём выводе), а "
    "падает только при первом реальном вызове — 'syntax error at or "
    "near \"$\"'. Особенно коварно для веток, управляемых редко "
    "переключаемыми флагами (например режимом отладки): отказ может "
    "случиться далеко не сразу после миграции. Нужно вручную развернуть "
    "нужную ветку в обычный код (или обычный IF, если решение должно "
    "приниматься во время выполнения, а не компиляции)."
)


def find_conditional_compilation(source: str) -> list[Finding]:
    """Detect Oracle's PL/SQL conditional-compilation directives ($IF/
    $ELSIF/$ELSE/$END). ora2pg copies them into the generated PL/pgSQL
    body verbatim as plain text -- PostgreSQL has no such preprocessor
    at all, so this is a syntax error at the first real call, not at
    CREATE time (ora2pg disables check_function_bodies in its own
    output). See docs/research/gap-035-conditional-compilation.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _COND_COMPILE_RE.finditer(clean):
        findings.append(
            Finding(
                detector="conditional_compilation",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet=m.group(0),
                message=_MESSAGE,
            )
        )

    return findings
