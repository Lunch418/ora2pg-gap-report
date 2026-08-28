import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_comments_only,
    mask_strings_and_comments,
)

# Oracle's alternative-quoting mechanism: q'<delim> ... <delim>'  (also
# spelled nq'...' for national character literals). Only the opening
# three characters are matched -- the closing delimiter depends on the
# opening one ([ pairs with ], { with }, ( with ), < with >, anything
# else with itself) and plsql_lex already implements that pairing for
# masking purposes; repeating it here would duplicate the rule with no
# gain, since the finding is about the literal *starting* at all.
_ALT_QUOTE_RE = re.compile(r"\bN?Q'(.)", re.IGNORECASE)

_MESSAGE = (
    "q'[...]' — альтернативные кавычки Oracle: способ записать строку с "
    "апострофами внутри, не удваивая их. ora2pg копирует такой литерал в "
    "вывод как есть (подтверждено реальным прогоном ora2pg 25.0 + "
    "PostgreSQL 16, docs/research/gap-062-alt-quote-literal.md). "
    "PostgreSQL этот синтаксис не понимает: q воспринимается как "
    "отдельный идентификатор, а дальше начинается обычный "
    "строковый литерал, и разбор уезжает — в PL/pgSQL-теле это "
    "'mismatched parentheses' при первом вызове (загрузка проходит "
    "чисто, потому что ora2pg выставляет check_function_bodies = false). "
    "Заменяется на обычный литерал с удвоенными апострофами или, что "
    "ближе по духу, на долларовые кавычки PostgreSQL: $q$it's a test$q$ "
    "— внутри них экранировать не нужно ничего."
)


def find_alt_quote_literals(source: str) -> list[Finding]:
    """Detect Oracle's q'...' / nq'...' alternative-quoting literals.
    ora2pg copies them through unchanged and PostgreSQL has no such
    syntax, so the generated code fails to parse. See
    docs/research/gap-062-alt-quote-literal.md.

    Matched against mask_comments_only() rather than the usual fully
    masked view: mask_strings_and_comments() understands q-quotes and
    blanks them out, which is exactly the text this detector exists to
    find, while the raw source would also match commented-out code."""
    clean = mask_strings_and_comments(source)
    literals = mask_comments_only(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _ALT_QUOTE_RE.finditer(literals):
        findings.append(
            Finding(
                detector="alt_quote_literal",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(source, m.start()),
                snippet=f"q'{m.group(1)}...",
                message=_MESSAGE,
            )
        )

    return findings
