import argparse
import dataclasses
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from .detectors.autonomous_tx import find_autonomous_transactions
from .detectors.bulk_collect import find_bulk_collect_usage
from .detectors.compound_triggers import find_compound_triggers
from .detectors.connect_by import find_connect_by_risks, guess_object_type, has_connect_by
from .detectors.database_link import find_database_link_references
from .detectors.dbms_utl_calls import find_dbms_utl_calls
from .detectors.flashback_query import find_flashback_queries
from .detectors.merge_delete_clause import find_merge_delete_clauses
from .detectors.model_clause import find_model_clauses
from .detectors.object_type import find_object_types
from .detectors.pivot_clause import find_pivot_clauses
from .detectors.with_function import find_with_function_clauses
from .effort_estimator import estimate_hours, ordered_counts, summarize_by_severity
from .models import Finding
from .ora2pg_wrapper import Ora2PgNotFoundError, Ora2PgRunError, run_estimate_cost
from .plsql_lex import enclosing_object_name_index, mask_strings_and_comments
from .report_generator import to_json, to_markdown
from .terminal_report import render as render_terminal

_DETECTORS = (
    find_autonomous_transactions,
    find_compound_triggers,
    find_dbms_utl_calls,
    find_merge_delete_clauses,
    find_bulk_collect_usage,
    find_database_link_references,
    find_model_clauses,
    find_pivot_clauses,
    find_object_types,
    find_with_function_clauses,
    find_flashback_queries,
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


def count_objects(source: str) -> int:
    """How many top-level Oracle objects (PACKAGE BODY, standalone
    PROCEDURE/FUNCTION, TRIGGER) this source declares — not lines, not
    findings, just what the file itself declares, via the same masking/
    attribution infrastructure the detectors use. Nested routines inside a
    package aren't counted separately: the package as a whole is the
    migration unit, same as Oracle's own object model.

    Counts every declaration, not distinct names: qualified_name_pattern()
    only captures the final (unqualified) name component, so deduplicating
    by name would silently collapse two genuinely different objects that
    happen to share a bare name in different schemas (hr.emp_pkg vs
    sales.emp_pkg) into one. A file re-declaring the exact same object
    twice (DROP + CREATE under the same name, as in
    docs/research/samples/compound_trigger_dlee.sql) is comparatively rare
    and only affects this display count, not any detector's findings."""
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    return sum(1 for _, kind, _ in index if kind in ("package", "standalone_routine", "trigger"))


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
        "--format",
        choices=("terminal", "markdown", "json"),
        default=None,
        help=(
            "Формат отчёта. По умолчанию — цветной вывод в терминал, если "
            "stdout это tty и не указан --output; иначе markdown."
        ),
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
            "Требует установленный ora2pg (не ставится через pip — это "
            "отдельный Perl-инструмент, см. README)."
        ),
    )
    parser.add_argument(
        "--ora2pg-bin",
        default="ora2pg",
        help="Путь к исполняемому файлу ora2pg (по умолчанию ищется в PATH)",
    )
    parser.add_argument(
        "--severity",
        choices=("high", "medium", "low"),
        default=None,
        help="Показать только находки с этим уровнем серьёзности",
    )
    parser.add_argument(
        "--object",
        default=None,
        help="Показать только находки для объектов, чьё имя содержит эту подстроку (без учёта регистра)",
    )
    return parser


def _apply_filters(findings: list[Finding], severity: str | None, object_substring: str | None) -> list[Finding]:
    if severity is not None:
        findings = [f for f in findings if f.severity == severity]
    if object_substring is not None:
        needle = object_substring.upper()
        findings = [f for f in findings if needle in f.object_name.upper()]
    return findings


def _connect_by_check(path: Path, source: str, ora2pg_bin: str) -> tuple[list[Finding], str | None]:
    """Returns (findings, warning) — warning is set instead of raising when
    ora2pg isn't available or fails, since this check is opt-in/best-effort
    by design (see docs/research/step0-show-report-baseline.md section 3:
    low priority for MVP)."""
    if not has_connect_by(source):
        return [], None
    try:
        output = run_estimate_cost(path, guess_object_type(source), ora2pg_bin=ora2pg_bin)
    except Ora2PgNotFoundError:
        return [], f"{path}: содержит CONNECT BY, но ora2pg не найден — проверка пропущена"
    except Ora2PgRunError as exc:
        return [], f"{path}: содержит CONNECT BY, но запуск ora2pg завершился ошибкой ({exc})"

    # `line` in each risk is a position inside ora2pg's *generated*
    # PostgreSQL output (a tempfile.TemporaryDirectory in run_estimate_cost,
    # already deleted by the time this returns) — it does not correspond to
    # any line in `path`. source_file=path is still correct (that's genuinely
    # the Oracle input that produced this), but stamping ora2pg's internal
    # line number onto it would point the user at an unrelated line in their
    # own file; 0 signals "not a line in this file" instead of a wrong one.
    # object_name/snippet (the enclosing routine and the exact bad LEVEL
    # reference) still identify the problem unambiguously without it.
    return [
        dataclasses.replace(f, source_file=str(path), line=0) for f in find_connect_by_risks(output)
    ], None


def _render(findings: list[Finding], fmt: str) -> str:
    if fmt == "json":
        return to_json(findings)

    counts = summarize_by_severity(findings)
    counts_text = ", ".join(f"{name}: {n}" for name, n in ordered_counts(counts))
    lo, hi = estimate_hours(findings)
    header = (
        "# Отчёт ora2pg-gap-report\n\n"
        f"Найдено проблемных объектов: {len(findings)} ({counts_text})\n\n"
        f"Грубая оценка ручной доработки: {lo:g}–{hi:g} ч. "
        "— неоткалиброванная эвристика по severity, не измерение "
        "(см. PROJECT_BRIEF.md).\n\n"
    )
    return header + to_markdown(findings)


def resolve_format(explicit_format: str | None, output: Path | None, stdout_is_tty: bool) -> str:
    """Pure resolution logic, kept separate from main() so the
    default-format behaviour is testable without a real terminal."""
    if explicit_format is not None:
        return explicit_format
    return "terminal" if (output is None and stdout_is_tty) else "markdown"


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    err_console = Console(stderr=True)

    fmt = resolve_format(args.format, args.output, sys.stdout.isatty())

    start_time = time.perf_counter()
    all_findings: list[Finding] = []
    objects_scanned = 0
    had_error = False
    for path in args.paths:
        if not path.is_file():
            err_console.print(f"[yellow]Пропущен (не найден):[/yellow] {escape(str(path))}")
            had_error = True
            continue
        try:
            source = path.read_text(errors="replace")
        except OSError as exc:
            err_console.print(
                f"[yellow]Пропущен (не читается: {escape(str(exc))}):[/yellow] {escape(str(path))}"
            )
            had_error = True
            continue
        objects_scanned += count_objects(source)
        all_findings.extend(
            dataclasses.replace(f, source_file=str(path)) for f in scan_source(source)
        )

        if args.check_connect_by:
            findings, warning = _connect_by_check(path, source, args.ora2pg_bin)
            all_findings.extend(findings)
            if warning:
                err_console.print(f"[yellow]{escape(warning)}[/yellow]")

    elapsed_seconds = time.perf_counter() - start_time
    all_findings = _apply_filters(all_findings, args.severity, args.object)
    _sort_findings(all_findings)

    if fmt == "terminal":
        if args.output:
            try:
                with args.output.open("w", encoding="utf-8") as fh:
                    render_terminal(
                        all_findings,
                        console=Console(file=fh),
                        elapsed_seconds=elapsed_seconds,
                        objects_scanned=objects_scanned,
                    )
            except OSError as exc:
                err_console.print(
                    f"[red]Не удалось записать отчёт в {escape(str(args.output))}: "
                    f"{escape(str(exc))}[/red]"
                )
                return 2
        else:
            render_terminal(all_findings, elapsed_seconds=elapsed_seconds, objects_scanned=objects_scanned)
    else:
        report = _render(all_findings, fmt)
        if args.output:
            try:
                args.output.write_text(report, encoding="utf-8")
            except OSError as exc:
                err_console.print(
                    f"[red]Не удалось записать отчёт в {escape(str(args.output))}: "
                    f"{escape(str(exc))}[/red]"
                )
                return 2
        else:
            print(report)

    return 2 if had_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
