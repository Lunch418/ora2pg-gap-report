import argparse
import dataclasses
import difflib
import sys
import time
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from . import i18n
from .autofix import fix_identity_double_parens
from .baseline import BaselineLoadError, diff_against_baseline, load_baseline, save_baseline
from .core import (
    _SEVERITY_ORDER,
    _connect_by_check,
    _expand_paths,
    _sort_findings,
    count_objects,
    scan_source,
)
from .effort_estimator import estimate_hours, ordered_counts, summarize_by_severity
from .gap_registry import gap_by_number, normalize_gap_number, research_doc_path, research_doc_url
from .models import Finding
from .report_generator import to_csv, to_html, to_json, to_markdown, to_sarif, to_verification_json
from .terminal_report import render as render_terminal
from .terminal_report import render_baseline_diff, render_verification
from .verification import verify_against_baseline


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

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str = argparse.SUPPRESS,
        default: str = argparse.SUPPRESS,
        help: str | None = None,
    ) -> None:
        super().__init__(option_strings=option_strings, dest=dest, default=default, nargs=0, help=help)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[object] | None,
        option_string: str | None = None,
    ) -> None:
        parser._print_message(f"{parser.prog} {_package_version()}\n", sys.stdout)
        parser.exit()


def _peek_lang_for_help(argv: list[str]) -> str | None:
    """Best-effort peek at an explicit --lang value in argv, so
    _build_arg_parser() can render --help/description text in the right
    language *before* argparse has actually parsed --lang out (argparse
    itself needs the parser already built to parse anything, including
    --lang -- the classic chicken-and-egg with translating --help text,
    previously flagged as unsolved in i18n.py's own module docstring;
    this is that solution). Deliberately narrow: only recognizes '--lang
    en'/'--lang ru' and '--lang=en'/'--lang=ru' -- good enough for
    choosing a display language for --help text, not a stand-in for
    argparse's own validation (an invalid or malformed --lang here just
    falls through to i18n.resolve_language()'s normal precedence, and
    argparse itself still rejects it properly once real parsing
    happens)."""
    for i, arg in enumerate(argv):
        if arg == "--lang" and i + 1 < len(argv) and argv[i + 1] in ("ru", "en"):
            return argv[i + 1]
        if arg.startswith("--lang=") and arg[len("--lang=") :] in ("ru", "en"):
            return arg[len("--lang=") :]
    return None


def _build_arg_parser(lang: str = "ru") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ora2pg-gap-report",
        description=i18n.t(lang, "help_description"),
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help=i18n.t(lang, "help_paths"),
    )
    parser.add_argument(
        "--version",
        action=_LazyVersionAction,
        help=i18n.t(lang, "help_version"),
    )
    parser.add_argument(
        "--explain",
        default=None,
        metavar="GAP-NNN",
        help=i18n.t(lang, "help_explain"),
    )
    parser.add_argument(
        "--format",
        choices=("terminal", "markdown", "json", "csv", "sarif", "html"),
        default=None,
        help=i18n.t(lang, "help_format"),
    )
    parser.add_argument("--output", type=Path, default=None, help=i18n.t(lang, "help_output"))
    parser.add_argument(
        "--check-connect-by",
        action="store_true",
        help=i18n.t(lang, "help_check_connect_by"),
    )
    parser.add_argument(
        "--ora2pg-bin",
        default="ora2pg",
        help=i18n.t(lang, "help_ora2pg_bin"),
    )
    parser.add_argument(
        "--severity",
        choices=("high", "medium", "low"),
        default=None,
        help=i18n.t(lang, "help_severity"),
    )
    parser.add_argument(
        "--object",
        default=None,
        help=i18n.t(lang, "help_object"),
    )
    parser.add_argument(
        "--save",
        type=Path,
        default=None,
        metavar="PATH",
        help=i18n.t(lang, "help_save"),
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        metavar="PATH",
        help=i18n.t(lang, "help_baseline"),
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help=i18n.t(lang, "help_verify"),
    )
    parser.add_argument(
        "--fail-on",
        choices=("high", "medium", "low"),
        default=None,
        metavar="SEVERITY",
        help=i18n.t(lang, "help_fail_on"),
    )
    parser.add_argument(
        "--lang",
        choices=("ru", "en"),
        default=None,
        help=i18n.t(lang, "help_lang"),
    )
    parser.add_argument(
        "--set-lang",
        action="store_true",
        help=i18n.t(lang, "help_set_lang"),
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help=i18n.t(lang, "help_tui"),
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help=i18n.t(lang, "help_fix"),
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help=i18n.t(lang, "help_write"),
    )
    return parser


def _apply_filters(findings: list[Finding], severity: str | None, object_substring: str | None) -> list[Finding]:
    if severity is not None:
        findings = [f for f in findings if f.severity == severity]
    if object_substring is not None:
        needle = object_substring.upper()
        findings = [f for f in findings if needle in f.object_name.upper()]
    return findings


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
    # None for most gaps so far -- a deliberate partial rollout, see
    # gap_registry.py's own failure_stage field docstring. No line at all
    # when unset, rather than an empty/placeholder one.
    stage_line = (
        i18n.t(lang, "explain_failure_stage_line", stage=i18n.t(lang, f"failure_stage_{gap.failure_stage}"))
        if gap.failure_stage is not None
        else None
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
        if stage_line is not None:
            console.print(stage_line)
        console.print(i18n.t(lang, "explain_see_github", url=research_doc_url(gap)))
        return 0

    console.print(Panel(Text(f"GAP-{gap.number} — {gap.detector}"), border_style="cyan"))
    console.print(version_line)
    if stage_line is not None:
        console.print(stage_line)
    console.print(doc_path.read_text(encoding="utf-8"))
    return 0


def _handle_verify(args: argparse.Namespace, err_console: Console, lang: str) -> int:
    """--verify: scans `args.paths` as ora2pg's *generated* PostgreSQL
    output (not Oracle source -- scan_source()'s detectors still work on
    it because the VERBATIM ones look for Oracle-syntax fragments that
    ora2pg copies unchanged, see verification.py) and compares against
    `args.baseline` (a --save snapshot from before the migration) at
    detector granularity. See verification.py's module docstring for why
    finding-level matching (file/object/snippet) doesn't survive the
    Oracle-to-PostgreSQL boundary."""
    # args.explain isn't checked here: main() dispatches --explain first
    # and returns before ever reaching this function, so by the time
    # we're here args.explain is always None. The --explain branch above
    # is the one that has to know about --verify (and does).
    conflicting = any(
        (args.save, args.fail_on, args.check_connect_by, args.fix, args.write, args.severity, args.object)
    )
    if conflicting:
        err_console.print(i18n.t(lang, "verify_conflict_error"))
        return 2
    if not args.baseline:
        err_console.print(i18n.t(lang, "verify_requires_baseline"))
        return 2
    if not args.paths:
        err_console.print(i18n.t(lang, "no_paths_error"))
        return 2

    verify_fmt = args.format if args.format is not None else "terminal"
    if verify_fmt not in ("terminal", "json"):
        err_console.print(i18n.t(lang, "verify_unsupported_format"))
        return 2

    try:
        baseline = load_baseline(args.baseline, lang=lang)
    except BaselineLoadError as exc:
        err_console.print(f"[red]{escape(str(exc))}[/red]")
        return 2

    paths_to_scan, empty_dirs = _expand_paths(args.paths)
    had_error = False
    for empty_dir in empty_dirs:
        err_console.print(i18n.t(lang, "empty_dir_warning", dir=escape(str(empty_dir))))
        had_error = True

    post_migration_findings: list[Finding] = []
    for path in paths_to_scan:
        if not path.is_file():
            err_console.print(i18n.t(lang, "skipped_not_found", path=escape(str(path))))
            had_error = True
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            err_console.print(
                i18n.t(lang, "skipped_unreadable", exc=escape(str(exc)), path=escape(str(path)))
            )
            had_error = True
            continue
        post_migration_findings.extend(
            dataclasses.replace(f, source_file=str(path)) for f in scan_source(source)
        )

    results = verify_against_baseline(baseline, post_migration_findings)

    if verify_fmt == "json":
        report = to_verification_json(results)
    else:
        report = None

    if args.output:
        try:
            if report is not None:
                args.output.write_text(report, encoding="utf-8")
            else:
                with args.output.open("w", encoding="utf-8") as fh:
                    render_verification(results, console=Console(file=fh), lang=lang)
        except OSError as exc:
            err_console.print(
                i18n.t(lang, "write_report_error", path=escape(str(args.output)), exc=escape(str(exc)))
            )
            return 2
    elif report is not None:
        print(report)
    else:
        render_verification(results, lang=lang)

    return 2 if had_error else 0


def _handle_fix(args: argparse.Namespace, out_console: Console, err_console: Console, lang: str) -> int:
    """--fix: applies autofix.py's mechanical fixes to `args.paths`, treated
    like --verify's inputs as ora2pg's *generated* PostgreSQL output, not
    Oracle source (see autofix.py's module docstring for why). Dry-run by
    default -- prints a unified diff and touches nothing on disk; --write is
    required to actually persist the fix."""
    conflicting = any(
        (
            args.fail_on,
            args.save,
            args.baseline,
            args.check_connect_by,
            args.severity,
            args.object,
            args.format,
            args.output,
        )
    )
    if conflicting:
        err_console.print(i18n.t(lang, "fix_conflict_error"))
        return 2
    if not args.paths:
        err_console.print(i18n.t(lang, "no_paths_error"))
        return 2

    paths_to_scan, empty_dirs = _expand_paths(args.paths)
    had_error = False
    for empty_dir in empty_dirs:
        err_console.print(i18n.t(lang, "empty_dir_warning", dir=escape(str(empty_dir))))
        had_error = True

    total_fixes = 0
    for path in paths_to_scan:
        if not path.is_file():
            err_console.print(i18n.t(lang, "skipped_not_found", path=escape(str(path))))
            had_error = True
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            err_console.print(
                i18n.t(lang, "skipped_unreadable", exc=escape(str(exc)), path=escape(str(path)))
            )
            had_error = True
            continue

        fixed, count = fix_identity_double_parens(source)
        if count == 0:
            out_console.print(i18n.t(lang, "fix_summary_clean", path=escape(str(path))))
            continue
        total_fixes += count

        if args.write:
            try:
                path.write_text(fixed, encoding="utf-8")
            except OSError as exc:
                err_console.print(
                    i18n.t(lang, "fix_write_error", path=escape(str(path)), exc=escape(str(exc)))
                )
                had_error = True
                continue
            out_console.print(i18n.t(lang, "fix_summary_written", path=escape(str(path)), count=count))
        else:
            out_console.print(i18n.t(lang, "fix_diff_header", path=escape(str(path)), count=count))
            diff = difflib.unified_diff(
                source.splitlines(keepends=True),
                fixed.splitlines(keepends=True),
                fromfile=str(path),
                tofile=str(path),
            )
            out_console.print("".join(diff), markup=False, highlight=False)

    if total_fixes and not args.write:
        out_console.print(i18n.t(lang, "fix_summary_dry_run_hint"))

    return 2 if had_error else 0


def main(argv: list[str] | None = None) -> int:
    raw_argv = argv if argv is not None else sys.argv[1:]
    help_lang = i18n.resolve_language(_peek_lang_for_help(raw_argv), interactive=False)
    args = _build_arg_parser(help_lang).parse_args(argv)
    err_console = Console(stderr=True)

    if args.set_lang:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            # The interactive picker reads a line from stdin -- without a
            # real terminal that's an immediate EOFError (cron/CI/Docker
            # RUN/`< /dev/null`), which would otherwise surface as a raw
            # Python traceback instead of this tool's normal clean error +
            # exit code 2.
            err_console.print(
                i18n.t(i18n.resolve_language(args.lang, interactive=False), "set_lang_not_interactive")
            )
            return 2
        chosen = i18n.prompt_language_interactively()
        i18n.save_language(chosen)
        Console().print(i18n.t(chosen, "lang_saved", chosen=chosen))
        return 0

    lang = i18n.resolve_language(
        args.lang, interactive=sys.stdin.isatty() and sys.stdout.isatty()
    )

    if args.tui:
        # Standalone mode, same pattern as --explain/--verify below: takes
        # at most one path (a starting point for the directory tree, not a
        # list to scan directly -- picking what to scan interactively is
        # the whole point), and none of the scan-shaping flags, which
        # would otherwise silently do nothing once inside the TUI.
        conflicting = (args.paths and len(args.paths) > 1) or any(
            (
                args.explain,
                args.fail_on,
                args.save,
                args.baseline,
                args.check_connect_by,
                args.verify,
                args.fix,
                args.write,
                args.severity,
                args.object,
                args.format,
                args.output,
            )
        )
        if conflicting:
            err_console.print(i18n.t(lang, "tui_conflict_error"))
            return 2
        start_path = None
        if args.paths:
            candidate = args.paths[0]
            if not candidate.exists():
                err_console.print(i18n.t(lang, "skipped_not_found", path=escape(str(candidate))))
                return 2
            start_path = candidate if candidate.is_dir() else candidate.parent
        try:
            from .tui_app import run_tui
        except ImportError:
            err_console.print(i18n.t(lang, "tui_not_installed"))
            return 2
        run_tui(start_path, lang)
        return 0

    if args.explain is not None:
        # --explain is a standalone lookup, not a scan -- silently ignoring
        # scan flags combined with it would be actively dangerous for
        # --fail-on/--save specifically: a stray "--explain GAP-NNN" tacked
        # onto a real CI invocation would otherwise short-circuit to exit 0
        # (or skip writing a baseline) without ever looking at the findings
        # those flags are there to act on, silently masking a real gate
        # failure instead of erroring on the nonsensical combination.
        conflicting = args.paths or any(
            (
                args.fail_on,
                args.save,
                args.baseline,
                args.check_connect_by,
                args.verify,
                args.fix,
                args.write,
                args.format,
                args.output,
                args.severity,
                args.object,
            )
        )
        if conflicting:
            err_console.print(i18n.t(lang, "explain_conflict_error"))
            return 2
        return _handle_explain(args.explain, Console(), err_console, lang)

    if args.verify:
        return _handle_verify(args, err_console, lang)

    if args.fix:
        return _handle_fix(args, Console(), err_console, lang)

    if args.write:
        # --write alone (without --fix) has nothing to do -- catch it here
        # rather than silently falling through to a normal scan that just
        # ignores an argument the user clearly meant to matter.
        err_console.print(i18n.t(lang, "fix_write_without_fix_error"))
        return 2

    if not args.paths:
        err_console.print(i18n.t(lang, "no_paths_error"))
        return 2

    # --save writes this run's findings, --baseline reads a *previous*
    # run's snapshot to diff against -- the same path for both means
    # --baseline reads back the file --save is about to overwrite with
    # this run's own result, silently comparing it against itself
    # (NEW/RESOLVED always 0, UNCHANGED always everything) regardless of
    # what actually changed.
    if args.save and args.baseline and args.save.resolve() == args.baseline.resolve():
        err_console.print(i18n.t(lang, "save_baseline_same_path_error", path=escape(str(args.save))))
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
            source = path.read_text(encoding="utf-8", errors="replace")
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
            findings, warning = _connect_by_check(path, source, args.ora2pg_bin, lang)
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
    if args.save and had_error:
        # A snapshot missing some of what was asked to be scanned (a
        # not-found file, an empty directory, an unreadable file) isn't
        # "ground truth for the schema" -- it's ground truth for whatever
        # scanning actually completed, silently. The next --baseline diff
        # against it would report the skipped files' findings as NEW the
        # moment the actual problem (why they were skipped) gets fixed,
        # not as what they really are: never captured in the first place.
        err_console.print(i18n.t(lang, "save_baseline_skipped_partial_scan", path=escape(str(args.save))))
    elif args.save:
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
