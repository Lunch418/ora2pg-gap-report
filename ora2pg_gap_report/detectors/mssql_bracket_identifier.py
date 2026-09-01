import re

from ..models import Finding
from ..mssql_lex import line_at, mask_strings_and_comments, normalize_name

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

_MESSAGE = (
    "Идентификаторы в квадратных скобках ([dbo].[Orders], [Id], [int]) "
    "— штатный способ записи имён в T-SQL, и именно так их выводит SSMS "
    "и Generate Scripts по умолчанию, то есть так выглядит практически "
    "любой реальный скрипт. При файловом экспорте (-M -i <файл>) ora2pg "
    "скобки не снимает: они остаются частью имени и потом ещё берутся в "
    "двойные кавычки. Из CREATE TABLE [dbo].[Orders] ( [Id] [int] ... ) "
    "получается CREATE TABLE \"[dbo]\".\"[orders]\" ( \"[id]\" [INT] ... ), "
    "то есть таблица с именем [orders] в схеме [dbo] и столбец типа "
    "[INT], которого не существует. Подтверждено реальным прогоном "
    "ora2pg 25.0 + PostgreSQL 16 (docs/research/"
    "gap-087-mssql-bracket-identifier.md): загрузка падает сразу — "
    "'syntax error at or near \"[\"'. Та же таблица, записанная без "
    "скобок, конвертируется корректно, так что дело именно в них. "
    "Причина видна в исходниках ora2pg: снятие скобок "
    "(s/[\\[\\]]+//g) есть в MSSQL.pm, но только в подпрограммах, "
    "работающих с живым подключением (_column_info, _get_views, "
    "_get_functions, _get_procedures, _column_attributes и другие) — "
    "файловый путь через -i до них не доходит. Отсюда и обход: либо "
    "экспортировать через живое подключение к SQL Server, либо снять "
    "скобки в скрипте до конвертации."
)


def find_mssql_bracket_identifiers(source: str) -> list[Finding]:
    """Detect bracket-delimited identifiers on T-SQL CREATE statements.
    ora2pg -M's file-based path never strips them -- the brackets end up
    inside the generated identifier, and inside type names -- so the DDL
    fails to load. One finding per CREATE, not per bracket. See
    docs/research/gap-087-mssql-bracket-identifier.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _BRACKETED_CREATE_RE.finditer(clean):
        findings.append(
            Finding(
                detector="mssql_bracket_identifier",
                severity="high",
                object_name=normalize_name(m.group(2)).upper(),
                line=line_at(clean, m.start()),
                snippet=f"CREATE {m.group(1).upper()} {m.group(2)}",
                message=_MESSAGE,
            )
        )

    return findings
