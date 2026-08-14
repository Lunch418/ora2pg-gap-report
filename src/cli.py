import argparse
import dataclasses
import sys
from pathlib import Path

from .detectors.autonomous_tx import find_autonomous_transactions
from .detectors.compound_triggers import find_compound_triggers
from .detectors.connect_by import find_connect_by_risks, has_connect_by
from .detectors.dbms_utl_calls import find_dbms_utl_calls
from .effort_estimator import estimate_hours, summarize_by_severity
from .models import Finding
from .ora2pg_wrapper import Ora2PgNotFoundError, Ora2PgRunError, run_estimate_cost
from .report_generator import to_json, to_markdown

_DETECTORS = (
    find_autonomous_transactions,
    find_compound_triggers,
    find_dbms_utl_calls,
)
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _sort_findings(findings: list[Finding]) -> None:
    findings.sort(key=lambda f: (_SEVERITY_ORDER.get(f.severity, 99), f.object_name, f.line))


def scan_source(source: str) -> list[Finding]:
    findings: list[Finding] = []
    for detector in _DETECTORS:
        findings.extend(detector(source))
    _sort_findings(findings)
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
    parser.add_argument(
        "--check-connect-by",
        action="store_true",
        help=(
            "Дополнительно: для файлов с CONNECT BY реально прогнать ora2pg и "
            "проверить сгенерированный WITH RECURSIVE на известный баг с LEVEL. "
            "Требует установленный ora2pg (не входит в requirements.txt — это "
            "отдельный Perl-инструмент, см. README)."
        ),
    )
    parser.add_argument(
        "--ora2pg-bin",
        default="ora2pg",
        help="Путь к исполняемому файлу ora2pg (по умолчанию ищется в PATH)",
    )
    return parser


def _connect_by_check(path: Path, source: str, ora2pg_bin: str) -> tuple[list[Finding], str | None]:
    """Returns (findings, warning) — warning is set instead of raising when
    ora2pg isn't available or fails, since this check is opt-in/best-effort
    by design (see docs/research/step0-show-report-baseline.md section 3:
    low priority for MVP)."""
    if not has_connect_by(source):
        return [], None
    try:
        output = run_estimate_cost(path, "PACKAGE", ora2pg_bin=ora2pg_bin)
    except Ora2PgNotFoundError:
        return [], f"{path}: содержит CONNECT BY, но ora2pg не найден — проверка пропущена"
    except Ora2PgRunError as exc:
        return [], f"{path}: содержит CONNECT BY, но запуск ora2pg завершился ошибкой ({exc})"
    return [
        dataclasses.replace(f, source_file=str(path)) for f in find_connect_by_risks(output)
    ], None


def _render(findings: list[Finding], fmt: str) -> str:
    if fmt == "json":
        return to_json(findings)

    counts = summarize_by_severity(findings)
    counts_text = ", ".join(f"{name}: {n}" for name, n in counts.items())
    lo, hi = estimate_hours(findings)
    header = (
        "# Отчёт ora2pg-gap-report\n\n"
        f"Найдено проблемных объектов: {len(findings)} ({counts_text})\n\n"
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
        try:
            source = path.read_text(errors="replace")
        except OSError as exc:
            print(f"Пропущен (не читается: {exc}): {path}", file=sys.stderr)
            had_error = True
            continue
        all_findings.extend(
            dataclasses.replace(f, source_file=str(path)) for f in scan_source(source)
        )

        if args.check_connect_by:
            findings, warning = _connect_by_check(path, source, args.ora2pg_bin)
            all_findings.extend(findings)
            if warning:
                print(warning, file=sys.stderr)

    _sort_findings(all_findings)
    report = _render(all_findings, args.format)

    if args.output:
        try:
            args.output.write_text(report)
        except OSError as exc:
            print(f"Не удалось записать отчёт в {args.output}: {exc}", file=sys.stderr)
            return 2
    else:
        print(report)

    return 2 if had_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
