import argparse
import sys
from pathlib import Path

from .detectors.autonomous_tx import find_autonomous_transactions
from .detectors.compound_triggers import find_compound_triggers
from .detectors.dbms_utl_calls import find_dbms_utl_calls
from .effort_estimator import estimate_hours, summarize_by_severity
from .models import Finding
from .report_generator import to_json, to_markdown

_DETECTORS = (
    find_autonomous_transactions,
    find_compound_triggers,
    find_dbms_utl_calls,
)
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def scan_source(source: str) -> list[Finding]:
    findings: list[Finding] = []
    for detector in _DETECTORS:
        findings.extend(detector(source))
    findings.sort(key=lambda f: (_SEVERITY_ORDER.get(f.severity, 99), f.object_name, f.line))
    return findings


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ora2pg-gap-report",
        description=(
            "Сканирует выгруженный Oracle DDL (PACKAGE BODY / TRIGGER) и "
            "показывает конкретные объекты, которые ora2pg не перенесёт "
            "корректно, и почему."
        ),
    )
    parser.add_argument(
        "paths", nargs="+", type=Path, help="Файлы с DDL для анализа (.sql/.pks/.pkb)"
    )
    parser.add_argument(
        "--format", choices=("markdown", "json"), default="markdown", help="Формат отчёта"
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="Куда сохранить отчёт (по умолчанию — stdout)"
    )
    return parser


def _render(findings: list[Finding], fmt: str) -> str:
    if fmt == "json":
        return to_json(findings)

    counts = summarize_by_severity(findings)
    lo, hi = estimate_hours(findings)
    header = (
        "# Отчёт ora2pg-gap-report\n\n"
        f"Найдено проблемных объектов: {len(findings)} "
        f"(high: {counts['high']}, medium: {counts['medium']}, low: {counts['low']})\n\n"
        f"Грубая оценка ручной доработки: {lo:g}–{hi:g} ч. "
        "— неоткалиброванная эвристика по severity, не измерение "
        "(см. PROJECT_BRIEF.md).\n\n"
    )
    return header + to_markdown(findings)


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    all_findings: list[Finding] = []
    had_error = False
    for path in args.paths:
        if not path.is_file():
            print(f"Пропущен (не найден): {path}", file=sys.stderr)
            had_error = True
            continue
        all_findings.extend(scan_source(path.read_text(errors="replace")))

    report = _render(all_findings, args.format)

    if args.output:
        args.output.write_text(report)
    else:
        print(report)

    return 2 if had_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
