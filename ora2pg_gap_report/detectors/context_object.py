import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern

_CONTEXT_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+(?:OR\s+REPLACE\s+)?CONTEXT"),
    re.IGNORECASE,
)

_MESSAGE = (
    "CREATE CONTEXT — объявление application context (часто основа "
    "VPD/row-level security через SYS_CONTEXT в связке с "
    "DBMS_SESSION.SET_CONTEXT). ora2pg не конвертирует эту конструкцию "
    "вообще — она полностью пропадает из вывода, без сгенерированного "
    "PostgreSQL-эквивалента (подтверждено реальным прогоном ora2pg, "
    "docs/research/gap-015-context.md). В логах есть только служебная "
    "строка уровня DEBUG ('unhandled line'), а не предупреждение — легко "
    "пропустить при реальной миграции. У PostgreSQL нет прямого аналога "
    "application context — обычно переписывается на "
    "current_setting()/set_config() с ручным управлением видимостью, или "
    "на Row-Level Security (CREATE POLICY) для сценария VPD."
)


def find_context_declarations(source: str) -> list[Finding]:
    """Detect Oracle CREATE CONTEXT declarations. ora2pg has no
    conversion path for these at all -- see
    docs/research/gap-015-context.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _CONTEXT_RE.finditer(clean):
        findings.append(
            Finding(
                detector="context_object",
                severity="medium",
                object_name=m.group(1).upper(),
                line=line_at(clean, m.start()),
                snippet="CREATE CONTEXT",
                message=_MESSAGE,
            )
        )

    return findings
