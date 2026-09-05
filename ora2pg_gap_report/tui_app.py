"""Interactive TUI (`--tui`): browse to a file/directory and scan it with
the mouse (or the keyboard — every widget here is reachable by Tab/Enter/
arrow keys too), instead of remembering CLI flags.

This is an *additional* way in, not a replacement for the flag-based CLI:
main() in cli.py still works exactly as before, for CI/scripts/anyone who'd
rather type a command than click through screens (see README's own
"Interactive mode" section for the reasoning behind offering both).

Optional dependency: requires `textual` (`pip install
"ora2pg-gap-report[tui]"`), not part of the core install -- same pattern as
`oracledb` for `--oracle`. cli.py's own `--tui` handling imports this module
lazily and prints a clear install hint on ImportError instead of a raw
traceback; nothing else in the package imports this module or `textual` at
all.

Covers the same ground the flag-based CLI does: scan one or more files/
directories, save the result as a baseline, compare against a previously
saved one, and --verify a post-migration PostgreSQL scan against a
pre-migration baseline -- same underlying functions (baseline.py,
verification.py) the CLI uses, just click-driven.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import cast

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
)

from . import i18n
from .baseline import BaselineDiff, BaselineLoadError, diff_against_baseline, load_baseline, save_baseline
from .core import (
    DIALECTS,
    connect_by_check,
    expand_paths,
    baseline_dialects,
    count_objects,
    scan_source,
)
from .core import sort_findings
from .effort_estimator import estimate_hours, ordered_counts, summarize_by_severity
from .gap_registry import gap_metadata
from . import messages
from .models import Finding
from .verification import DetectorVerification, NewInOutput, new_in_output, verify_against_baseline

# Dracula's own published accent colors (draculatheme.com/contribute)
# for error/warning/success -- not the plain named "red"/"yellow"/"green"
# Rich would otherwise pick, which look harsh and don't match the app's
# Dracula theme (see GapReportApp.theme below) at all. Dracula ships as
# one of Textual's own built-in themes, already tuned for contrast on a
# dark background -- picking a maintained, tested palette here beats
# hand-rolling colors and hoping they read well.
_SEVERITY_STYLE = {"high": "bold #FF5555", "medium": "bold #F1FA8C", "low": "bold #50FA7B"}
_VERIFY_STATUS_STYLE = {
    "still_present": "bold #FF5555",
    "not_detected": "bold #50FA7B",
    "not_verifiable": "dim",
    # Not one of DetectorVerification's three statuses: rows for detectors
    # the baseline never had (the conversion introduced the construct),
    # shown in the same table because they answer the same user question
    # -- "what is wrong with the generated output" -- and a second table
    # on this screen would push the first one off a short terminal.
    "new_in_output": "bold #F1FA8C",
}

# Each language's own name, not translated cross-wise (same convention as
# i18n.py's own prompt_language_interactively -- a language picker is more
# discoverable shown in each language's own script than in whichever
# language happens to be selected already).
_LANG_OPTIONS = [("English", "en"), ("Русский", "ru")]


def _dialect_options() -> list[tuple[str, str]]:
    # Source-dialect names are fixed technical vocabulary, exactly like
    # the severity levels below -- shown as-is in both languages rather
    # than translated, and read straight from core.DIALECTS so a new
    # dialect appears in the picker without touching this module.
    return [(d, d) for d in DIALECTS]


def _severity_options(lang: str) -> list[tuple[str, str]]:
    # "high"/"medium"/"low" are deliberately not translated -- fixed
    # technical vocabulary everywhere else in this project (--severity's
    # own CLI choices, col_severity's "Severity" header even in Russian,
    # NEW/RESOLVED/UNCHANGED), not prose.
    return [
        (i18n.t(lang, "tui_severity_all"), "all"),
        (i18n.t(lang, "tui_severity_only", level="high"), "high"),
        (i18n.t(lang, "tui_severity_only", level="medium"), "medium"),
        (i18n.t(lang, "tui_severity_only", level="low"), "low"),
    ]


def scan_paths(
    paths: list[Path],
    check_connect_by: bool = False,
    ora2pg_bin: str = "ora2pg",
    lang: str = "ru",
    dialect: str = "oracle",
) -> tuple[list[Finding], int, list[str]]:
    """One or more files/directories in, findings out -- the same read ->
    scan_source() -> stamp source_file -> count_objects() sequence cli.py's
    own main() runs per path, just not sharing that loop directly (it's
    entangled with argparse's Namespace). Returns (findings, objects_scanned,
    warnings) instead of printing anything -- this module has no opinion on
    how a caller shows a warning, unlike cli.py's err_console.print() calls."""
    findings: list[Finding] = []
    objects_scanned = 0
    warnings: list[str] = []

    expanded, empty_dirs = expand_paths(paths)
    for empty_dir in empty_dirs:
        warnings.append(i18n.t(lang, "tui_warning_no_files_under", dir=empty_dir))

    seen: set[Path] = set()
    for file_path in expanded:
        if file_path in seen:
            # The same file reachable through two different selected paths
            # (a directory and one of its own files, both queued in a
            # multi-select) -- scan it once, not twice.
            continue
        seen.add(file_path)
        if not file_path.is_file():
            warnings.append(i18n.t(lang, "tui_warning_not_found", path=file_path))
            continue
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            warnings.append(i18n.t(lang, "tui_warning_could_not_read", path=file_path, exc=exc))
            continue
        # Same two-level isolation as cli.py's own scan loop, for the same
        # reason plus one that only applies here: an exception escaping a
        # @work(thread=True) worker doesn't just lose the scan, it takes
        # the whole Textual app down with it. A warning in the list the
        # caller already renders is a far better outcome than a dead UI.
        detector_errors: list[tuple[str, Exception]] = []
        try:
            objects_scanned += count_objects(source)
            file_findings = [
                dataclasses.replace(f, source_file=str(file_path))
                for f in scan_source(source, dialect=dialect, errors=detector_errors)
            ]
        except Exception as exc:
            warnings.append(
                i18n.t(
                    lang,
                    "tui_warning_scan_error",
                    path=file_path,
                    exc_type=type(exc).__name__,
                    exc=exc,
                )
            )
            continue

        if detector_errors:
            first_name, first_exc = detector_errors[0]
            names = ", ".join(name for name, _ in detector_errors[:3])
            if len(detector_errors) > 3:
                names += f" (+{len(detector_errors) - 3})"
            warnings.append(
                i18n.t(
                    lang,
                    "tui_warning_detector_error",
                    names=names,
                    path=file_path,
                    exc_type=type(first_exc).__name__,
                    exc=first_exc,
                )
            )

        findings.extend(file_findings)
        if check_connect_by:
            connect_by_findings, warning = connect_by_check(file_path, source, ora2pg_bin, lang)
            findings.extend(connect_by_findings)
            if warning:
                warnings.append(warning)

    sort_findings(findings)
    return findings, objects_scanned, warnings


def scan_path(
    path: Path, lang: str = "ru", dialect: str = "oracle"
) -> tuple[list[Finding], int, list[str]]:
    """One file or one directory in, findings out -- a thin single-path
    convenience wrapper around scan_paths(), kept as its own name because
    most callers (including the majority of this module's own tests) only
    ever have one path in hand."""
    return scan_paths([path], lang=lang, dialect=dialect)


# Screen[T] and App[T] are parameterised by what they *return* when
# dismissed; none of these hand a value back to a caller, so None is
# the accurate parameter rather than a placeholder.
class ScanScreen(Screen[None]):
    """Landing screen: pick one or more paths in the tree, choose
    severity/language and any optional checks (CONNECT BY, baseline
    comparison, --verify), press Scan."""

    CSS = """
    #tree-label { padding: 1 2 0 2; color: $text-muted; text-style: italic; }
    DirectoryTree { height: 1fr; margin: 1 2; border: round $panel-lighten-1; padding: 1; }
    #controls { height: auto; padding: 1 2; }
    /* Per-select widths, not one shared 26: three pickers plus the Scan
       button have to fit an 80-column terminal (the narrowest this app
       targets, and what App.run_test() gives the TUI tests). Each is
       sized to its own longest label -- "All severities" at 14 for
       severity, "Русский" at 7 for language, "oracle" at 6 for dialect
       -- rather than every one paying for the widest. */
    #controls Select { margin-right: 2; }
    #dialect-select { width: 12; }
    #severity-select { width: 20; }
    #lang-select { width: 13; }
    #controls Button { margin-top: 0; }
    #multi-select-controls { height: auto; padding: 0 2; }
    #multi-select-controls Button { margin-right: 2; }
    #multi-select-controls Checkbox { margin-top: 0; }
    #baseline-controls { height: auto; padding: 0 2 1 2; }
    #baseline-controls Input { width: 1fr; margin-right: 2; }
    #baseline-controls Checkbox { margin-top: 0; }
    #status { height: auto; padding: 0 3 1 3; color: $text-muted; }
    """

    def __init__(self, start_path: Path, lang: str = "ru") -> None:
        super().__init__()
        self._start_path = start_path
        self.lang = lang
        self.selected_path: Path | None = None
        self.selected_paths: list[Path] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(i18n.t(self.lang, "tui_tree_label"), id="tree-label")
        yield DirectoryTree(str(self._start_path), id="tree")
        with Horizontal(id="controls"):
            yield Select(_dialect_options(), value="oracle", id="dialect-select", allow_blank=False)
            yield Select(_severity_options(self.lang), value="all", id="severity-select", allow_blank=False)
            yield Select(_LANG_OPTIONS, value=self.lang, id="lang-select", allow_blank=False)
            yield Button(i18n.t(self.lang, "tui_scan_btn"), id="scan-btn", variant="primary")
        with Horizontal(id="multi-select-controls"):
            yield Button(i18n.t(self.lang, "tui_add_to_selection_btn"), id="add-path-btn")
            yield Button(i18n.t(self.lang, "tui_clear_selection_btn"), id="clear-paths-btn")
            yield Checkbox(i18n.t(self.lang, "tui_connect_by_checkbox"), id="connect-by-checkbox")
        with Horizontal(id="baseline-controls"):
            yield Input(placeholder=i18n.t(self.lang, "tui_baseline_input_placeholder"), id="baseline-input")
            yield Checkbox(i18n.t(self.lang, "tui_verify_checkbox"), id="verify-checkbox")
        yield Static(i18n.t(self.lang, "tui_status_nothing_selected"), id="status")
        yield Footer()

    def _update_status(self) -> None:
        # Text(...), not an f-string handed to Static.update(): a selected
        # path can contain anything the filesystem allows, brackets
        # included, and Static parses plain strings as Textual markup --
        # "/data/notes[/archive]/x.sql" would otherwise raise MarkupError
        # (confirmed the hard way, see CHANGELOG). Same reasoning as
        # terminal_report.py's own Text(...) wrapping of scanned-content
        # table cells.
        lines = []
        if self.selected_path is not None:
            lines.append(i18n.t(self.lang, "tui_status_highlighted", path=self.selected_path))
        if self.selected_paths:
            listing = "\n".join(f"  - {p}" for p in self.selected_paths)
            lines.append(
                i18n.t(self.lang, "tui_status_queued", n=len(self.selected_paths), listing=listing)
            )
        if not lines:
            lines.append(i18n.t(self.lang, "tui_status_nothing_selected"))
        self.query_one("#status", Static).update(Text("\n".join(lines)))

    def _show_status_error(self, message: str) -> None:
        # Style via Text(..., style=...), not inline markup around an
        # f-string -- `message` can carry an exception's own text (e.g. a
        # baseline load error quoting the bad file's content), which must
        # never be parsed as markup either.
        self.query_one("#status", Static).update(Text(message, style="bold #FF5555"))

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self.selected_path = event.path
        self._update_status()

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self.selected_path = event.path
        self._update_status()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "add-path-btn":
            if self.selected_path is None:
                self._show_status_error(i18n.t(self.lang, "tui_error_pick_in_tree_first"))
                return
            if self.selected_path not in self.selected_paths:
                self.selected_paths.append(self.selected_path)
            self._update_status()
            return

        if button_id == "clear-paths-btn":
            self.selected_paths = []
            self._update_status()
            return

        if button_id != "scan-btn":
            return

        paths = list(self.selected_paths) if self.selected_paths else (
            [self.selected_path] if self.selected_path is not None else []
        )
        if not paths:
            self._show_status_error(i18n.t(self.lang, "tui_error_pick_first"))
            return

        # cast(), not a runtime check: Select.value's declared type is
        # broader (Any | NoSelection) to cover allow_blank=True selects,
        # but both these selects are built with allow_blank=False and a
        # fixed set of str options -- NoSelection is genuinely
        # unreachable here.
        severity = cast(str, self.query_one("#severity-select", Select).value)
        lang = cast(str, self.query_one("#lang-select", Select).value)
        dialect = cast(str, self.query_one("#dialect-select", Select).value)
        check_connect_by = self.query_one("#connect-by-checkbox", Checkbox).value
        verify_mode = self.query_one("#verify-checkbox", Checkbox).value
        baseline_value = self.query_one("#baseline-input", Input).value.strip()
        baseline_path = baseline_value or None

        if verify_mode and baseline_path is None:
            self._show_status_error(i18n.t(lang, "tui_error_verify_needs_baseline"))
            return
        if check_connect_by and dialect != "oracle":
            # Same Oracle-only restriction cli.py enforces for
            # --check-connect-by: the check runs ora2pg in Oracle mode and
            # looks for Oracle-only syntax, so on another dialect it is a
            # no-op dressed up as a check.
            self._show_status_error(i18n.t(lang, "connect_by_oracle_only", dialect=dialect))
            return
        if verify_mode and check_connect_by:
            # Same conflict cli.py's own --verify rejects (see
            # verify_conflict_error): --verify scans generated PostgreSQL
            # output, where a CONNECT BY check against Oracle source
            # doesn't make sense.
            self._show_status_error(i18n.t(lang, "tui_error_verify_conflicts_connect_by"))
            return

        if verify_mode:
            assert baseline_path is not None  # ruled out by the check above
            self.query_one("#status", Static).update(i18n.t(lang, "tui_status_verifying"))
            self._run_verify(paths, Path(baseline_path), lang, dialect)
        else:
            self.query_one("#status", Static).update(i18n.t(lang, "tui_status_scanning"))
            self._run_scan(paths, severity, lang, check_connect_by, baseline_path, dialect)

    @work(thread=True)
    def _run_scan(
        self,
        paths: list[Path],
        severity: str,
        lang: str,
        check_connect_by: bool,
        baseline_path: str | None,
        dialect: str = "oracle",
    ) -> None:
        # An exception escaping a @work(thread=True) worker doesn't just
        # lose the scan -- it tears down the whole Textual app, dropping
        # the user back to a bare terminal with a traceback. scan_paths()
        # already isolates per file and per detector; this is the outer
        # boundary for everything else in the worker (baseline loading,
        # translation, screen construction). Deliberately broad, same
        # trade-off cli.py's main() documents.
        try:
            self._run_scan_impl(paths, severity, lang, check_connect_by, baseline_path, dialect)
        except Exception as exc:
            self.app.call_from_thread(
                self._show_status_error,
                i18n.t(lang, "tui_worker_crashed", exc_type=type(exc).__name__, exc=exc),
            )

    def _run_scan_impl(
        self,
        paths: list[Path],
        severity: str,
        lang: str,
        check_connect_by: bool,
        baseline_path: str | None,
        dialect: str = "oracle",
    ) -> None:
        all_findings, objects_scanned, warnings = scan_paths(
            paths, check_connect_by=check_connect_by, lang=lang, dialect=dialect
        )

        baseline_diff: BaselineDiff | None = None
        if baseline_path is not None:
            try:
                baseline = load_baseline(Path(baseline_path), lang=lang)
            except BaselineLoadError as exc:
                self.app.call_from_thread(
                    self._show_status_error,
                    i18n.t(lang, "tui_error_couldnt_load_baseline", exc=exc),
                )
                return
            baseline_diff = diff_against_baseline(all_findings, baseline)

        display_findings = all_findings
        if severity != "all":
            display_findings = [f for f in display_findings if f.severity == severity]

        scanned_label = ", ".join(str(p) for p in paths)
        self.app.call_from_thread(
            self.app.push_screen,
            ResultsScreen(display_findings, all_findings, objects_scanned, warnings, lang, scanned_label, baseline_diff),
        )

    @work(thread=True)
    def _run_verify(
        self, paths: list[Path], baseline_path: Path, lang: str, dialect: str = "oracle"
    ) -> None:
        # Same outer boundary as _run_scan above -- see its comment.
        try:
            self._run_verify_impl(paths, baseline_path, lang, dialect)
        except Exception as exc:
            self.app.call_from_thread(
                self._show_status_error,
                i18n.t(lang, "tui_worker_crashed", exc_type=type(exc).__name__, exc=exc),
            )

    def _run_verify_impl(
        self, paths: list[Path], baseline_path: Path, lang: str, dialect: str = "oracle"
    ) -> None:
        try:
            baseline = load_baseline(baseline_path, lang=lang)
        except BaselineLoadError as exc:
            self.app.call_from_thread(
                self._show_status_error, i18n.t(lang, "tui_error_couldnt_load_baseline", exc=exc)
            )
            return

        # Which dialect to re-scan with comes from the baseline, not from
        # the picker -- same rule (and same three failure cases) as
        # cli.py's _handle_verify, so the two modes can't disagree about
        # what a given snapshot means.
        found_dialects, unknown_detectors = baseline_dialects(baseline)
        if unknown_detectors:
            self.app.call_from_thread(
                self._show_status_error,
                i18n.t(lang, "verify_unknown_detectors", detectors=", ".join(unknown_detectors)),
            )
            return
        if len(found_dialects) > 1:
            self.app.call_from_thread(
                self._show_status_error,
                i18n.t(lang, "verify_mixed_dialects", dialects=", ".join(sorted(found_dialects))),
            )
            return
        baseline_dialect = next(iter(found_dialects), dialect)
        if dialect != "oracle" and dialect != baseline_dialect:
            self.app.call_from_thread(
                self._show_status_error,
                i18n.t(
                    lang,
                    "verify_dialect_mismatch",
                    requested=dialect,
                    baseline_dialect=baseline_dialect,
                ),
            )
            return

        # Same loop cli.py's own _handle_verify() runs, deliberately not
        # shared with scan_paths(): --verify treats `paths` as ora2pg's
        # *generated* PostgreSQL output, not Oracle source, so none of
        # scan_paths()'s Oracle-specific extras (--check-connect-by) apply.
        expanded, empty_dirs = expand_paths(paths)
        warnings = [i18n.t(lang, "tui_warning_no_files_under", dir=d) for d in empty_dirs]
        post_migration_findings: list[Finding] = []
        for file_path in expanded:
            if not file_path.is_file():
                warnings.append(i18n.t(lang, "tui_warning_not_found", path=file_path))
                continue
            try:
                source = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                warnings.append(i18n.t(lang, "tui_warning_could_not_read", path=file_path, exc=exc))
                continue
            detector_errors: list[tuple[str, Exception]] = []
            post_migration_findings.extend(
                dataclasses.replace(f, source_file=str(file_path))
                for f in scan_source(source, dialect=baseline_dialect, errors=detector_errors)
            )
            if detector_errors:
                first_name, first_exc = detector_errors[0]
                names = ", ".join(name for name, _ in detector_errors[:3])
                if len(detector_errors) > 3:
                    names += f" (+{len(detector_errors) - 3})"
                warnings.append(
                    i18n.t(
                        lang,
                        "tui_warning_detector_error",
                        names=names,
                        path=file_path,
                        exc_type=type(first_exc).__name__,
                        exc=first_exc,
                    )
                )

        results = verify_against_baseline(baseline, post_migration_findings)
        introduced = new_in_output(baseline, post_migration_findings)
        scanned_label = ", ".join(str(p) for p in paths)
        self.app.call_from_thread(
            self.app.push_screen,
            VerifyResultsScreen(results, warnings, scanned_label, lang, introduced),
        )


class ResultsScreen(Screen[None]):
    """Findings from one scan: a summary bar, a table, and a details panel
    that fills in when a row is selected -- same information --explain and
    the terminal report already show (message + GAP-NNN + failure_stage),
    just click-driven instead of read off a static panel. Also offers
    saving this scan's findings as a --save baseline snapshot, and shows a
    NEW/RESOLVED/UNCHANGED summary when the scan was run with a baseline
    file to compare against."""

    BINDINGS = [("escape", "app.pop_screen", "Back")]

    CSS = """
    /* max-height + overflow-y, not just height: auto: "Scanned <path>"
       wraps to a different number of lines depending on how long the
       scanned path's absolute string is -- which depends on where the
       repo is checked out, not just on what's actually being scanned.
       Confirmed the hard way: this screen's layout passed locally (a
       short /workspace/... checkout path) and then failed in CI on every
       Python version (a longer runner checkout path wrapped the summary
       one line taller, pushing #back-btn's region below the 80x24 test
       viewport that had fit it fine locally). Capping the height here
       makes the rest of the layout's position independent of checkout
       path length instead of "hope it never wraps more than expected". */
    #summary {
        height: auto; max-height: 25%; overflow-y: auto; padding: 1 2;
        border: round $primary; margin: 1 2; background: $panel;
    }
    /* 2fr/1fr, not a fixed height for #detail: a fixed height (tried
       first at 14) doesn't scale down on a small terminal -- at the
       80x24 Textual itself defaults to for headless/test runs, the rest
       of this screen's fixed-height chrome (header, summary, save-
       baseline row, back button, footer) plus a 14-row detail box
       genuinely doesn't fit, pushing #back-btn below the visible
       viewport entirely. Sharing the remaining space proportionally
       guarantees both boxes fit whatever the real terminal size is,
       just with different proportions. */
    #findings-table { height: 2fr; margin: 0 2; border: round $panel-lighten-1; }
    #detail {
        height: 1fr; border: round $accent; margin: 1 2; padding: 1 2;
        overflow-y: auto; background: $panel;
    }
    #baseline-save-controls { height: auto; padding: 0 2 1 2; }
    #baseline-save-controls Input { width: 1fr; margin-right: 2; }
    #back-btn { margin: 0 2 1 2; }
    """

    def __init__(
        self,
        findings: list[Finding],
        all_findings: list[Finding],
        objects_scanned: int,
        warnings: list[str],
        lang: str,
        scanned_path: str,
        baseline_diff: BaselineDiff | None = None,
    ) -> None:
        super().__init__()
        self.findings = findings
        # The full, unfiltered scan result -- what --save/--baseline act on
        # in the CLI too (see cli.py's own comment on `all_findings`):
        # a baseline snapshot is meant as ground truth for the schema, not
        # whatever --severity/--object narrowed this screen's table down to.
        self.all_findings = all_findings
        self.objects_scanned = objects_scanned
        self.warnings = warnings
        self.lang = lang
        self.scanned_path = scanned_path
        self.baseline_diff = baseline_diff
        # Set by the "Save baseline" button, folded into #summary instead of
        # its own row -- a screen already tight enough at 80x24 to have
        # pushed #back-btn out of the visible viewport once (see the CSS
        # comment on #detail below) doesn't have a spare row for it. A
        # Text, not a markup string: it carries a user-typed path or an
        # OSError's own text, neither safe to run through markup parsing.
        self._save_status: Text | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self._summary_text(), id="summary")
        table: DataTable[str] = DataTable(id="findings-table", cursor_type="row")
        yield table
        yield Static(i18n.t(self.lang, "tui_results_select_row_hint"), id="detail")
        with Horizontal(id="baseline-save-controls"):
            yield Input(
                placeholder=i18n.t(self.lang, "tui_save_baseline_input_placeholder"),
                id="save-baseline-input",
            )
            yield Button(i18n.t(self.lang, "tui_save_baseline_btn"), id="save-baseline-btn")
        yield Button(i18n.t(self.lang, "tui_back_to_scan_btn"), id="back-btn")
        yield Footer()

    def _summary_text(self) -> Text:
        # Built as a Text, appended to piece by piece, not as an f-string
        # with inline [style] markup: scanned_path and warnings carry
        # scanned-content/filesystem text verbatim (a path with brackets
        # would raise MarkupError on Static.update() otherwise -- same
        # class of bug terminal_report.py's own Text(...) wrapping avoids).
        # Only the style spans below (Text(..., style=...)) are markup;
        # everything else is plain appended text, never parsed.
        if not self.findings:
            text = Text(i18n.t(self.lang, "tui_scanned_no_findings", path=self.scanned_path))
        else:
            counts = summarize_by_severity(self.findings)
            counts_text = ", ".join(f"{name}: {n}" for name, n in ordered_counts(counts))
            lo, hi = estimate_hours(self.findings)
            text = Text(
                i18n.t(
                    self.lang,
                    "tui_scanned_summary",
                    path=self.scanned_path,
                    objects=self.objects_scanned,
                    count=len(self.findings),
                    counts_text=counts_text,
                    lo=lo,
                    hi=hi,
                )
            )
        if self.baseline_diff is not None:
            # NEW/RESOLVED/UNCHANGED stay untranslated words here, same as
            # terminal_report.py's own render_baseline_diff() -- fixed
            # status vocabulary, not prose (see _severity_options()'s own
            # reasoning for the same choice with high/medium/low).
            d = self.baseline_diff
            text.append("\n")
            text.append("Baseline: ", style="bold")
            text.append(f"{len(d.new)} new", style="#FF5555")
            text.append(", ")
            text.append(f"{len(d.resolved)} resolved", style="#50FA7B")
            text.append(f", {d.unchanged_count} unchanged")
        if self.warnings:
            text.append("\n")
            text.append(" / ".join(self.warnings), style="#F1FA8C")
        if self._save_status is not None:
            text.append("\n")
            text.append(self._save_status)
        return text

    def on_mount(self) -> None:
        table = self.query_one("#findings-table", DataTable)
        # Just the basename, not the full path handed to --tui (usually a
        # long absolute path from the DirectoryTree, repeated on nearly
        # every row of a single-file scan) -- the full path is already in
        # the summary bar above. Without this, File alone can push
        # Detector/GAP off the right edge of the table entirely, hiding
        # the one thing this table exists to surface.
        #
        # Reuses col_severity/col_file/col_object/col_line/col_detector --
        # the same terminal_report.py findings-table headers, not a
        # tui_-prefixed duplicate. "GAP" stays a literal, untranslated
        # column name here too, matching md_table_header/html_table_header.
        table.add_columns(
            i18n.t(self.lang, "col_severity"),
            i18n.t(self.lang, "col_file"),
            i18n.t(self.lang, "col_object"),
            i18n.t(self.lang, "col_line"),
            i18n.t(self.lang, "col_detector"),
            "GAP",
        )
        for i, f in enumerate(self.findings):
            gap_number, _ = gap_metadata(f.detector)
            # Text(...) per cell, not markup strings: object_name/file name
            # come straight from the scanned Oracle source (a quoted
            # identifier like "my[table]" is legal Oracle and would
            # otherwise be parsed as a style tag) -- same reasoning as
            # terminal_report.py's own table. Only Severity gets an actual
            # style, passed as Text's own style= kwarg, never inline markup.
            table.add_row(
                Text(f.severity, style=_SEVERITY_STYLE.get(f.severity, "")),
                Text(Path(f.source_file).name if f.source_file else "—"),
                Text(f.object_name),
                Text(str(f.line)),
                Text(f.detector),
                Text(f"GAP-{gap_number}" if gap_number else "—"),
                key=str(i),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_key_value = event.row_key.value
        assert row_key_value is not None  # every row is added with key=str(i) in on_mount()
        index = int(row_key_value)
        f = self.findings[index]
        gap_number, failure_stage = gap_metadata(f.detector)
        # GAP-NNN/stage comes right after the header, before the message
        # body -- not after it. f.message can run to several wrapped
        # lines (see e.g. bulk_collect's), and #detail has a fixed height
        # with overflow-y: auto -- put the GAP reference last and a long
        # enough message pushes the one thing this panel exists to show
        # (when does this actually break) below the visible area with no
        # obvious indication there's more to scroll to.
        #
        # Built as a Text, appended piece by piece: f.object_name/f.message
        # can carry scanned-content text verbatim (a quoted Oracle
        # identifier, or a detector message that echoes a captured snippet)
        # -- never safe to hand to Static.update() as an f-string with
        # inline markup. Only ref/stage_label are markup-safe (built
        # entirely from our own GAP-NNN numbering and i18n dict), so those
        # are the only pieces styled here.
        text = Text()
        text.append(f.detector, style="bold")
        text.append(f" ({f.object_name}:{f.line})")
        if gap_number is not None:
            ref = f"GAP-{gap_number}"
            if failure_stage is not None:
                # Same short label terminal_report.py's own explanation
                # panel uses -- respects the language picked for this
                # scan, same as f.message already does.
                stage_label = i18n.t(self.lang, f"failure_stage_short_{failure_stage}")
                text.append(f"\n{ref} · {stage_label}", style="dim")
            else:
                text.append(f"\n{ref}", style="dim")
        text.append("\n\n")
        text.append(messages.text(f.message_id, self.lang))
        self.query_one("#detail", Static).update(text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back-btn":
            self.app.pop_screen()
            return
        if event.button.id == "save-baseline-btn":
            # Text(..., style=...), not markup around an f-string: `value`
            # is whatever the user typed and `exc` is an OSError's own
            # text (could quote the path back), neither safe to parse as
            # markup.
            value = self.query_one("#save-baseline-input", Input).value.strip()
            if not value:
                self._save_status = Text(
                    i18n.t(self.lang, "tui_error_enter_path_first"), style="bold #FF5555"
                )
            else:
                try:
                    save_baseline(self.all_findings, Path(value))
                except OSError as exc:
                    self._save_status = Text(
                        i18n.t(self.lang, "tui_error_couldnt_save", exc=exc), style="bold #FF5555"
                    )
                else:
                    self._save_status = Text(
                        i18n.t(self.lang, "tui_saved_findings", n=len(self.all_findings), path=value),
                        style="#50FA7B",
                    )
            self.query_one("#summary", Static).update(self._summary_text())


class VerifyResultsScreen(Screen[None]):
    """--verify inside the TUI: the same detector-level STILL_PRESENT/
    NOT_DETECTED/NOT_VERIFIABLE comparison terminal_report.py's own
    render_verification() draws with Rich, redrawn here as a DataTable --
    see verification.py's module docstring for why detector-level (not
    finding-level) matching is the only thing that survives the
    Oracle-to-PostgreSQL boundary."""

    BINDINGS = [("escape", "app.pop_screen", "Back")]

    CSS = """
    #verify-summary { height: auto; padding: 1 2; border: round $primary; margin: 1 2; background: $panel; }
    #verify-table { height: 1fr; margin: 0 2 1 2; border: round $panel-lighten-1; }
    #verify-back-btn { margin: 0 2 1 2; }
    #verify-footer-note { height: auto; padding: 0 3 1 3; color: $text-muted; }
    """

    def __init__(
        self,
        results: list[DetectorVerification],
        warnings: list[str],
        scanned_path: str,
        lang: str = "ru",
        new_in_output: list[NewInOutput] | None = None,
    ) -> None:
        super().__init__()
        self.results = results
        self.warnings = warnings
        self.scanned_path = scanned_path
        self.lang = lang
        self.new_in_output = new_in_output or []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self._summary_text(), id="verify-summary")
        yield DataTable(id="verify-table", cursor_type="row")
        # Same footer disclaimer text as terminal_report.py's own
        # render_verification() -- reuses its i18n key rather than a
        # tui_-prefixed duplicate.
        yield Static(i18n.t(self.lang, "verify_footer_note"), id="verify-footer-note")
        yield Button(i18n.t(self.lang, "tui_back_to_scan_btn"), id="verify-back-btn")
        yield Footer()

    def _summary_text(self) -> Text:
        # Text(...), not an f-string with inline markup: scanned_path and
        # warnings carry scanned-path/filesystem text verbatim -- same
        # reasoning as ResultsScreen._summary_text().
        counts = {"still_present": 0, "not_detected": 0, "not_verifiable": 0}
        for r in self.results:
            counts[r.status] = counts.get(r.status, 0) + 1
        text = Text(
            i18n.t(
                self.lang,
                "tui_verify_summary",
                path=self.scanned_path,
                n=len(self.results),
                still_present=counts["still_present"],
                not_detected=counts["not_detected"],
                not_verifiable=counts["not_verifiable"],
            )
        )
        if self.warnings:
            text.append("\n")
            text.append(" / ".join(self.warnings), style="#F1FA8C")
        return text

    def on_mount(self) -> None:
        table = self.query_one("#verify-table", DataTable)
        # Reuses terminal_report.py's own verify_col_* headers, same
        # reasoning as ResultsScreen.on_mount()'s col_* reuse above.
        table.add_columns(
            i18n.t(self.lang, "verify_col_detector"),
            i18n.t(self.lang, "verify_col_gap"),
            i18n.t(self.lang, "verify_col_before"),
            i18n.t(self.lang, "verify_col_after"),
            i18n.t(self.lang, "verify_col_status"),
        )
        for r in self.results:
            table.add_row(
                Text(r.detector),
                Text(f"GAP-{r.gap_number}" if r.gap_number else "—"),
                Text(str(r.baseline_count)),
                Text(str(r.post_migration_count) if r.status != "not_verifiable" else "—"),
                Text(r.status.upper(), style=_VERIFY_STATUS_STYLE.get(r.status, "")),
            )
        for e in self.new_in_output:
            # "Before" is "—", not 0: the detector isn't in the baseline
            # at all, which is a different statement from "the baseline
            # says it found none of these".
            table.add_row(
                Text(e.detector),
                Text(f"GAP-{e.gap_number}" if e.gap_number else "—"),
                Text("—"),
                Text(str(e.count)),
                Text("NEW_IN_OUTPUT", style=_VERIFY_STATUS_STYLE["new_in_output"]),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "verify-back-btn":
            self.app.pop_screen()


class GapReportApp(App[None]):
    """Entry point for `ora2pg-gap-report --tui`. See run_tui() below for
    the actual launch (handles the "textual isn't installed" case one
    level up, in cli.py, before this module is even imported)."""

    # TITLE stays the tool's own name, not translated -- same as every
    # other proper noun in this project's output (e.g. i18n.py's own
    # picker never translates "English"/"Русский" either). SUB_TITLE is
    # set per-instance in __init__ instead (below), since it needs `lang`,
    # not known yet at class-definition time.
    TITLE = "ora2pg-gap-report"
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, start_path: Path | None = None, lang: str = "ru") -> None:
        super().__init__()
        self._start_path = start_path or Path.cwd()
        self.lang = lang
        self.sub_title = i18n.t(lang, "tui_app_subtitle")
        # Dracula (draculatheme.com) -- one of Textual's own built-in
        # themes, not the library's generic default: high-contrast purple
        # on near-black, the option the project's own maintainer picked
        # after comparing it side by side with five other built-in themes.
        # Severity colors above (_SEVERITY_STYLE) are pulled straight from
        # Dracula's own published accents, not picked independently, so
        # they read as part of the same palette rather than clashing with it.
        self.theme = "dracula"

    def on_mount(self) -> None:
        self.push_screen(ScanScreen(self._start_path, self.lang))


def run_tui(start_path: Path | None = None, lang: str = "ru") -> None:
    GapReportApp(start_path=start_path, lang=lang).run()
