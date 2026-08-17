import argparse
import dataclasses
import sys
import time
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from . import i18n
from .baseline import BaselineLoadError, diff_against_baseline, load_baseline, save_baseline
from .detectors.autonomous_tx import find_autonomous_transactions
from .detectors.bulk_collect import find_bulk_collect_usage
from .detectors.collection_type import find_collection_types
from .detectors.compound_triggers import find_compound_triggers
from .detectors.connect_by import find_connect_by_risks, guess_object_type, has_connect_by
from .detectors.connect_by_nocycle import find_connect_by_nocycle_or_order_siblings
from .detectors.context_object import find_context_declarations
from .detectors.cross_apply import find_apply_joins
from .detectors.database_link import find_database_link_references
from .detectors.dbms_utl_calls import find_dbms_utl_calls
from .detectors.external_table import find_external_tables
from .detectors.flashback_query import find_flashback_queries
from .detectors.global_temp_table import find_global_temp_tables_without_delete_rows
from .detectors.identity_column import find_identity_columns_with_options
from .detectors.insert_all import find_multitable_inserts
from .detectors.invisible_column import find_invisible_columns
from .detectors.invisible_index import find_invisible_indexes
from .detectors.json_table import find_json_table_calls
from .detectors.materialized_view_log import find_materialized_view_logs
from .detectors.merge_delete_clause import find_merge_delete_clauses
from .detectors.model_clause import find_model_clauses
from .detectors.object_type import find_object_types
from .detectors.oracle_text import find_oracle_text_usage
from .detectors.pivot_clause import find_pivot_clauses
from .detectors.read_only_table import find_read_only_tables
from .detectors.recursive_with import find_recursive_with_missing_keyword
from .detectors.sql_macro import find_sql_macros
from .detectors.table_partitioning import find_dropped_table_partitioning
from .detectors.with_function import find_with_function_clauses
from .effort_estimator import estimate_hours, ordered_counts, summarize_by_severity
from .gap_registry import gap_by_number, normalize_gap_number, research_doc_path, research_doc_url
from .models import Finding
from .ora2pg_wrapper import Ora2PgNotFoundError, Ora2PgRunError, run_estimate_cost
from .plsql_lex import enclosing_object_name_index, mask_strings_and_comments
from .report_generator import to_csv, to_html, to_json, to_markdown, to_sarif
from .terminal_report import render as render_terminal
from .terminal_report import render_baseline_diff

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
    find_global_temp_tables_without_delete_rows,
    find_dropped_table_partitioning,
    find_connect_by_nocycle_or_order_siblings,
    find_context_declarations,
    find_multitable_inserts,
    find_json_table_calls,
    find_external_tables,
    find_sql_macros,
    find_invisible_columns,
    find_collection_types,
    find_apply_joins,
    find_oracle_text_usage,
    find_recursive_with_missing_keyword,
    find_invisible_indexes,
    find_read_only_tables,
    find_materialized_view_logs,
    find_identity_columns_with_options,
)
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
_DDL_SUFFIXES = (".sql", ".pks", ".pkb")


def _package_version() -> str:
    try:
        return _pkg_version("ora2pg-gap-report")
    except PackageNotFoundError:
        # Running from a source checkout that was never `pip install`-ed
        # (editable or otherwise) — no installed distribution to read a
        # version from, so there's nothing meaningful to report but also
        # no reason to crash a --version call over it.
        return "unknown (not installed)"


class _LazyVersionAction(argparse.Action):
    """Same effect as argparse's built-in action="version", but resolves
    the version string only when --version is actually passed. The
    built-in action takes a pre-formatted string, which forces
    _package_version() (an importlib.metadata distribution lookup) to run
    unconditionally at parser-construction time -- i.e. on every single
    CLI invocation, not just the rare one that asks for it."""

    def __init__(self, option_strings, dest=argparse.SUPPRESS, default=argparse.SUPPRESS, help=None):
        super().__init__(option_strings=option_strings, dest=dest, default=default, nargs=0, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        parser._print_message(f"{parser.prog} {_package_version()}\n", sys.stdout)
        parser.exit()


def _sort_findings(findings: list[Finding]) -> None:
    findings.sort(key=lambda f: (_SEVERITY_ORDER.get(f.severity, 99), f.object_name, f.line))


def scan_source(source: str) -> list[Finding]:
    findings: list[Finding] = []
    for detector in _DETECTORS:
        findings.extend(detector(source))
    _sort_findings(findings)
    return findings


def count_objects(source: str) -> int:
    """How many top-level Oracle objects (PACKAGE / PACKAGE BODY, standalone
    PROCEDURE/FUNCTION, TRIGGER, VIEW) this source declares — not lines, not
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
    and only affects this display count, not any detector's findings. A
    package whose spec *and* body are both present in the same file counts
    as 2 for the same reason -- both are real, separate 'package' entries
    in enclosing_object_name_index(), and deduplicating them back into one
    logical package would need name-tracking this function deliberately
    doesn't do, for the same low-stakes-display-count reasoning."""
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    return sum(
        1 for _, kind, _ in index if kind in ("package", "standalone_routine", "trigger", "view")
    )


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
        "paths",
        nargs="*",
        type=Path,
        help=(
            "Файлы с DDL для анализа (.sql/.pks/.pkb) и/или директории — "
            "директория сканируется рекурсивно на файлы с этими "
            "расширениями. Не нужны вместе с --explain."
        ),
    )
    parser.add_argument(
        "--version",
        action=_LazyVersionAction,
        help="Показать установленную версию и выйти",
    )
    parser.add_argument(
        "--explain",
        default=None,
        metavar="GAP-NNN",
        help=(
            "Показать research-документ конкретного gap'а из реестра (например, GAP-023 или "
            "просто 023) и выйти — без сканирования файлов. Самостоятельная команда: нельзя "
            "сочетать с путями к файлам, --fail-on, --save, --baseline или --check-connect-by."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("terminal", "markdown", "json", "csv", "sarif", "html"),
        default=None,
        help=(
            "Формат отчёта. По умолчанию — цветной вывод в терминал, если "
            "stdout это tty и не указан --output; иначе markdown. sarif — "
            "SARIF 2.1.0, для GitHub/GitLab code scanning. html — "
            "самодостаточная HTML-страница (без внешних ресурсов), для "
            "показа заказчику/руководству."
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
    parser.add_argument(
        "--save",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Сохранить находки этого прогона как baseline-снапшот в PATH (для последующего "
            "сравнения через --baseline). Снапшот — все находки, независимо от --severity/--object; "
            "эти флаги влияют только на то, что выводится в отчёте."
        ),
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Сравнить находки этого прогона с ранее сохранённым --save снапшотом: NEW/RESOLVED/"
            "UNCHANGED. Сравнение тоже считается по всем находкам, независимо от --severity/--object."
        ),
    )
    parser.add_argument(
        "--fail-on",
        choices=("high", "medium", "low"),
        default=None,
        metavar="SEVERITY",
        help=(
            "Завершиться с кодом 1, если среди находок есть хотя бы одна с этим уровнем серьёзности "
            "или выше (high выше medium выше low) — для CI-гейта. Оценивается по всем находкам, "
            "независимо от --severity/--object, чтобы фильтр вывода не маскировал провал гейта."
        ),
    )
    parser.add_argument(
        "--lang",
        choices=("ru", "en"),
        default=None,
        help=(
            "Язык вывода для этого запуска (не сохраняется). По умолчанию: сохранённый через "
            "--set-lang выбор, иначе переменная окружения ORA2PG_GAP_REPORT_LANG, иначе "
            "интерактивный выбор при первом запуске в реальном терминале, иначе русский."
        ),
    )
    parser.add_argument(
        "--set-lang",
        action="store_true",
        help="Открыть выбор языка и сохранить его как язык по умолчанию для будущих запусков, затем выйти.",
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


def _render(findings: list[Finding], fmt: str, lang: str = "ru") -> str:
    if fmt == "json":
        return to_json(findings)
    if fmt == "csv":
        return to_csv(findings)
    if fmt == "sarif":
        return to_sarif(findings, tool_version=_package_version())
    if fmt == "html":
        return to_html(findings, lang=lang)

    counts = summarize_by_severity(findings)
    counts_text = ", ".join(f"{name}: {n}" for name, n in ordered_counts(counts))
    lo, hi = estimate_hours(findings)
    header = (
        i18n.t(lang, "markdown_report_title")
        + i18n.t(lang, "markdown_findings_found", n=len(findings), counts=counts_text)
        + i18n.t(lang, "markdown_effort_estimate", lo=lo, hi=hi)
    )
    return header + to_markdown(findings, lang=lang)


def _expand_paths(paths: list[Path]) -> tuple[list[Path], list[Path]]:
    """Expand any directories in `paths` into the .sql/.pks/.pkb files they
    contain (recursively, sorted for deterministic output, extension match
    case-insensitive since exported DDL sometimes carries uppercase
    extensions e.g. from Windows tooling), leaving plain files and
    nonexistent paths untouched -- a nonexistent path still needs to reach
    main()'s existing is_file() check so its "not found" warning keeps
    firing the same way it always has. Returns (files_to_scan,
    directories_with_no_matching_files) so main() can warn about the
    latter -- silently scanning zero files from a directory the user
    pointed at on purpose would be a confusing, warning-free no-op.

    Deduplicates by resolved absolute path, so the same file reached twice
    (e.g. 'schema/ schema/logger.pkb', or two directory arguments that
    overlap) is scanned and reported once, not once per way it was named
    -- otherwise every count (objects_scanned, findings, effort hours)
    would silently double."""
    expanded: list[Path] = []
    empty_dirs: list[Path] = []
    seen: set[Path] = set()

    def _add(candidate: Path) -> None:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            expanded.append(candidate)

    for path in paths:
        if path.is_dir():
            found = sorted(
                p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in _DDL_SUFFIXES
            )
            if not found:
                empty_dirs.append(path)
            for p in found:
                _add(p)
        else:
            _add(path)
    return expanded, empty_dirs


def resolve_format(explicit_format: str | None, output: Path | None, stdout_is_tty: bool) -> str:
    """Pure resolution logic, kept separate from main() so the
    default-format behaviour is testable without a real terminal."""
    if explicit_format is not None:
        return explicit_format
    return "terminal" if (output is None and stdout_is_tty) else "markdown"


def _handle_explain(raw_ref: str, console: Console, err_console: Console, lang: str = "ru") -> int:
    number = normalize_gap_number(raw_ref)
    gap = gap_by_number(number) if number is not None else None
    if gap is None:
        err_console.print(i18n.t(lang, "explain_unknown_gap", ref=escape(raw_ref)))
        return 2

    version_line = i18n.t(
        lang, "confirmed_versions", ora2pg_version=gap.ora2pg_version, postgresql_version=gap.postgresql_version
    )

    doc_path = research_doc_path(gap)
    if doc_path is None:
        # docs/research/ isn't shipped in the pip-installed package (see
        # gap_registry.py's module docstring) -- only a source checkout has
        # it on disk. Falling back to a GitHub link still gets the user to
        # the same content instead of a bare "not found". Note: the
        # research doc itself (when found locally, below) is only ever
        # shown in Russian -- translating docs/research/ is out of scope
        # for this module, see its docstring.
        console.print(i18n.t(lang, "explain_doc_not_local", number=gap.number, detector=gap.detector))
        console.print(version_line)
        console.print(i18n.t(lang, "explain_see_github", url=research_doc_url(gap)))
        return 0

    console.print(Panel(Text(f"GAP-{gap.number} — {gap.detector}"), border_style="cyan"))
    console.print(version_line)
    console.print(doc_path.read_text(encoding="utf-8"))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    err_console = Console(stderr=True)

    if args.set_lang:
        chosen = i18n.prompt_language_interactively()
        i18n.save_language(chosen)
        Console().print(i18n.t(chosen, "lang_saved", chosen=chosen))
        return 0

    lang = i18n.resolve_language(
        args.lang, interactive=sys.stdin.isatty() and sys.stdout.isatty()
    )

    if args.explain is not None:
        # --explain is a standalone lookup, not a scan -- silently ignoring
        # scan flags combined with it would be actively dangerous for
        # --fail-on/--save specifically: a stray "--explain GAP-NNN" tacked
        # onto a real CI invocation would otherwise short-circuit to exit 0
        # (or skip writing a baseline) without ever looking at the findings
        # those flags are there to act on, silently masking a real gate
        # failure instead of erroring on the nonsensical combination.
        conflicting = args.paths or any(
            (args.fail_on, args.save, args.baseline, args.check_connect_by)
        )
        if conflicting:
            err_console.print(i18n.t(lang, "explain_conflict_error"))
            return 2
        return _handle_explain(args.explain, Console(), err_console, lang)

    if not args.paths:
        err_console.print(i18n.t(lang, "no_paths_error"))
        return 2

    fmt = resolve_format(args.format, args.output, sys.stdout.isatty())

    start_time = time.perf_counter()
    all_findings: list[Finding] = []
    objects_scanned = 0
    had_error = False

    paths_to_scan, empty_dirs = _expand_paths(args.paths)
    for empty_dir in empty_dirs:
        err_console.print(i18n.t(lang, "empty_dir_warning", dir=escape(str(empty_dir))))
        had_error = True

    for path in paths_to_scan:
        if not path.is_file():
            err_console.print(i18n.t(lang, "skipped_not_found", path=escape(str(path))))
            had_error = True
            continue
        try:
            source = path.read_text(errors="replace")
        except OSError as exc:
            err_console.print(
                i18n.t(lang, "skipped_unreadable", exc=escape(str(exc)), path=escape(str(path)))
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
    _sort_findings(all_findings)

    # Single point where a finding's message gets swapped for its English
    # counterpart (a no-op when lang == "ru") -- every renderer downstream
    # (terminal/markdown/json/csv/sarif/html) then sees a consistent
    # language with no per-format translation logic of its own. Done before
    # --save/--baseline/--fail-on/display filtering, all of which key off
    # detector/source_file/object_name/snippet/severity, never message --
    # see baseline.py's group_key() docstring -- so this has no effect on
    # any of them.
    if lang == "en":
        all_findings = [
            dataclasses.replace(f, message=i18n.translate_message(f.message, lang))
            for f in all_findings
        ]

    # --save/--baseline/--fail-on all act on the full, unfiltered scan
    # result (`all_findings`) rather than what --severity/--object narrow
    # the *displayed* report down to (`display_findings`, below) -- a
    # baseline snapshot is meant as ground truth for the schema, and a CI
    # gate silently muted by an unrelated display filter would be a much
    # worse surprise than a gate that's a little noisier than expected.
    if args.save:
        try:
            save_baseline(all_findings, args.save)
        except OSError as exc:
            err_console.print(
                i18n.t(lang, "save_baseline_error", path=escape(str(args.save)), exc=escape(str(exc)))
            )
            return 2

    baseline_diff = None
    if args.baseline:
        try:
            baseline = load_baseline(args.baseline, lang=lang)
        except BaselineLoadError as exc:
            err_console.print(f"[red]{escape(str(exc))}[/red]")
            return 2
        baseline_diff = diff_against_baseline(all_findings, baseline)

    display_findings = _apply_filters(all_findings, args.severity, args.object)

    if fmt == "terminal":
        if args.output:
            try:
                with args.output.open("w", encoding="utf-8") as fh:
                    render_terminal(
                        display_findings,
                        console=Console(file=fh),
                        elapsed_seconds=elapsed_seconds,
                        objects_scanned=objects_scanned,
                        lang=lang,
                    )
            except OSError as exc:
                err_console.print(
                    i18n.t(lang, "write_report_error", path=escape(str(args.output)), exc=escape(str(exc)))
                )
                return 2
        else:
            render_terminal(
                display_findings,
                elapsed_seconds=elapsed_seconds,
                objects_scanned=objects_scanned,
                lang=lang,
            )
    else:
        report = _render(display_findings, fmt, lang=lang)
        if args.output:
            try:
                args.output.write_text(report, encoding="utf-8")
            except OSError as exc:
                err_console.print(
                    i18n.t(lang, "write_report_error", path=escape(str(args.output)), exc=escape(str(exc)))
                )
                return 2
        else:
            print(report)

    # Printed to stderr regardless of --format: it's supplementary
    # human-facing context, not part of whatever structured payload
    # --format produced on stdout (json/csv/sarif are meant to be piped
    # or redirected as-is).
    if baseline_diff is not None:
        render_baseline_diff(baseline_diff, console=err_console, lang=lang)

    if had_error:
        return 2

    if args.fail_on is not None:
        threshold = _SEVERITY_ORDER[args.fail_on]
        failing = [f for f in all_findings if _SEVERITY_ORDER.get(f.severity, 99) <= threshold]
        if failing:
            err_console.print(
                i18n.t(lang, "gate_failed", n=len(failing), sev=args.fail_on)
            )
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
