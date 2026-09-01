import re

from ..models import Finding
from ..mssql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_strings_and_comments,
)

# `UPDATE <target> SET`, bounded and non-greedy so the match can never
# run past the end of its own statement into the next one's SET.
_PATTERN_RE = re.compile(r"\bUPDATE\s+[^;]{0,120}?\bSET\b", re.IGNORECASE)

_MESSAGE = (
    "UPDATE ... SET — обычное обновление строк. ora2pg (-M) путает это "
    "SET с одноимённым оператором присваивания переменной в T-SQL (SET "
    "@x = 1) и переписывает конструкцию по правилам присваивания: само "
    "слово SET из запроса пропадает, а первое присваивание получает := "
    "вместо = (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL "
    "16, docs/research/gap-089-mssql-update-set.md). Из UPDATE orders "
    "SET amount = @x, nm = \'y\' WHERE id = 1 получается UPDATE orders "
    "amount := p_x, nm = \'y\' WHERE id = 1. Загрузка проходит чисто — "
    "ora2pg выставляет в своём выводе check_function_bodies = false, — а "
    "при первом же реальном вызове процедура падает с \'syntax error at "
    "or near \":=\"\'. Под это попадает каждый UPDATE в каждой процедуре, "
    "так что после конвертации их придётся просмотреть все: правится "
    "возвратом к обычному SQL — UPDATE <таблица> SET <столбец> = "
    "<значение>."
)


def find_mssql_update_set(source: str) -> list[Finding]:
    """Detect T-SQL UPDATE ... SET statements. ora2pg -M mistakes the
    SET for T-SQL's variable-assignment SET, deletes the keyword and
    turns the first assignment's `=` into `:=`, producing
    `UPDATE t col := val` -- invalid in PL/pgSQL, so the routine loads
    cleanly and fails on its first call. See docs/research/
    gap-089-mssql-update-set.md."""
    clean = mask_strings_and_comments(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for m in _PATTERN_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_update_set",
                severity="high",
                object_name=enclosing_object_name(name_index, m.start()),
                line=line_at(clean, m.start()),
                snippet="UPDATE ... SET",
                message=_MESSAGE,
            )
        )

    return findings
