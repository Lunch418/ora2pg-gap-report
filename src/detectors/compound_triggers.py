import re

from ..models import Finding
from ..plsql_lex import mask_strings_and_comments

_TRIGGER_START_RE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:EDITIONABLE\s+|NONEDITIONABLE\s+)?"
    r"TRIGGER\s+(?:\"?\w+\"?\.)?\"?(\w+)\"?",
    re.IGNORECASE,
)
_COMPOUND_RE = re.compile(r"\bCOMPOUND\s+TRIGGER\b", re.IGNORECASE)

_MESSAGE = (
    "COMPOUND TRIGGER: секции BEFORE STATEMENT / BEFORE EACH ROW / "
    "AFTER EACH ROW / AFTER STATEMENT внутри одного триггера. У ora2pg нет "
    "отдельного пути конвертации для этого синтаксиса. В файловом режиме "
    "(-t TRIGGER -i file.sql) его regex-парсер (read_trigger_from_file) "
    "рассчитан на классическую форму 'ON <table> [FOR EACH ROW] "
    "[WHEN (...)] BEGIN...END' и на составном триггере тихо возвращает "
    "0 найденных триггеров — без единой ошибки или предупреждения "
    "(эмпирически подтверждено, docs/research/step0-show-report-baseline.md, "
    "раздел 5). В режиме живого подключения счётчик объектов SHOW_REPORT "
    "покажет этот триггер как обычный валидный (данные берутся из каталога "
    "Oracle, а не из попытки конвертации) — то есть само число объектов "
    "проблему не выдаст. По структуре export_trigger() в Ora2Pg.pm крайне "
    "вероятно, что и в живом режиме конвертация тела COMPOUND TRIGGER даёт "
    "синтаксически неверный или тихо испорченный код. Нужен ручной перенос "
    "— как правило, на несколько независимых обычных триггеров "
    "(BEFORE/AFTER × STATEMENT/ROW) с общим состоянием через пакетную "
    "переменную или временную таблицу вместо секций компаунд-триггера."
)


def find_compound_triggers(source: str) -> list[Finding]:
    """Detect CREATE [OR REPLACE] TRIGGER ... COMPOUND TRIGGER declarations.

    Bounds each trigger by the next CREATE TRIGGER statement (or end of
    file) rather than full block matching — Oracle does not support nested
    trigger declarations, so this is exact, not an approximation.
    """
    clean = mask_strings_and_comments(source)
    matches = list(_TRIGGER_START_RE.finditer(clean))

    findings: list[Finding] = []
    for idx, match in enumerate(matches):
        boundary = matches[idx + 1].start() if idx + 1 < len(matches) else len(clean)
        span = clean[match.end() : boundary]

        compound_match = _COMPOUND_RE.search(span)
        if not compound_match:
            continue

        absolute_pos = match.end() + compound_match.start()
        line_no = clean.count("\n", 0, absolute_pos) + 1

        findings.append(
            Finding(
                detector="compound_triggers",
                severity="high",
                object_name=match.group(1).upper(),
                line=line_no,
                snippet=compound_match.group(0).strip(),
                message=_MESSAGE,
            )
        )

    return findings
