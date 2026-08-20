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
from .cli import _connect_by_check, _expand_paths, count_objects, scan_source
from .cli import _sort_findings as sort_findings
from .effort_estimator import estimate_hours, ordered_counts, summarize_by_severity
from .gap_registry import gap_metadata
from .models import Finding
from .verification import DetectorVerification, verify_against_baseline

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
}

_SEVERITY_OPTIONS = [("All severities", "all"), ("High only", "high"), ("Medium only", "medium"), ("Low only", "low")]
_LANG_OPTIONS = [("Russian output", "ru"), ("English output", "en")]


def scan_paths(
    paths: list[Path],
    check_connect_by: bool = False,
    ora2pg_bin: str = "ora2pg",
    lang: str = "ru",
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

    expanded, empty_dirs = _expand_paths(paths)
    for empty_dir in empty_dirs:
        warnings.append(f"No .sql/.pks/.pkb files found under {empty_dir}")

    seen: set[Path] = set()
    for file_path in expanded:
        if file_path in seen:
            # The same file reachable through two different selected paths
            # (a directory and one of its own files, both queued in a
            # multi-select) -- scan it once, not twice.
            continue
        seen.add(file_path)
        if not file_path.is_file():
            warnings.append(f"Not found: {file_path}")
            continue
        try:
            source = file_path.read_text(errors="replace")
        except OSError as exc:
            warnings.append(f"Could not read {file_path}: {exc}")
            continue
        objects_scanned += count_objects(source)
        findings.extend(
            dataclasses.replace(f, source_file=str(file_path)) for f in scan_source(source)
        )
        if check_connect_by:
            connect_by_findings, warning = _connect_by_check(file_path, source, ora2pg_bin, lang)
            findings.extend(connect_by_findings)
            if warning:
                warnings.append(warning)

    sort_findings(findings)
    return findings, objects_scanned, warnings


def scan_path(path: Path) -> tuple[list[Finding], int, list[str]]:
    """One file or one directory in, findings out -- a thin single-path
    convenience wrapper around scan_paths(), kept as its own name because
    most callers (including the majority of this module's own tests) only
    ever have one path in hand."""
    return scan_paths([path])


class ScanScreen(Screen):
    """Landing screen: pick one or more paths in the tree, choose
    severity/language and any optional checks (CONNECT BY, baseline
    comparison, --verify), press Scan."""

    CSS = """
    #tree-label { padding: 1 2 0 2; color: $text-muted; text-style: italic; }
    DirectoryTree { height: 1fr; margin: 1 2; border: round $panel-lighten-1; padding: 1; }
    #controls { height: auto; padding: 1 2; }
    #controls Select { width: 26; margin-right: 2; }
    #controls Button { margin-top: 0; }
    #multi-select-controls { height: auto; padding: 0 2; }
    #multi-select-controls Button { margin-right: 2; }
    #multi-select-controls Checkbox { margin-top: 0; }
    #baseline-controls { height: auto; padding: 0 2 1 2; }
    #baseline-controls Input { width: 1fr; margin-right: 2; }
    #baseline-controls Checkbox { margin-top: 0; }
    #status { height: auto; padding: 0 3 1 3; color: $text-muted; }
    """

    def __init__(self, start_path: Path) -> None:
        super().__init__()
        self._start_path = start_path
        self.selected_path: Path | None = None
        self.selected_paths: list[Path] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Pick a .sql/.pks/.pkb file, or a directory to scan recursively:", id="tree-label")
        yield DirectoryTree(str(self._start_path), id="tree")
        with Horizontal(id="controls"):
            yield Select(_SEVERITY_OPTIONS, value="all", id="severity-select", allow_blank=False)
            yield Select(_LANG_OPTIONS, value="ru", id="lang-select", allow_blank=False)
            yield Button("Scan", id="scan-btn", variant="primary")
        with Horizontal(id="multi-select-controls"):
            yield Button("Add to selection", id="add-path-btn")
            yield Button("Clear selection", id="clear-paths-btn")
            yield Checkbox("Check CONNECT BY (requires ora2pg)", id="connect-by-checkbox")
        with Horizontal(id="baseline-controls"):
            yield Input(placeholder="Baseline file (optional -- compare or verify against it)", id="baseline-input")
            yield Checkbox("Verify mode (scan as post-migration output)", id="verify-checkbox")
        yield Static("Nothing selected yet.", id="status")
        yield Footer()

    def _update_status(self) -> None:
        lines = []
        if self.selected_path is not None:
            lines.append(f"Highlighted: {self.selected_path}")
        if self.selected_paths:
            listing = "\n".join(f"  - {p}" for p in self.selected_paths)
            lines.append(f"{len(self.selected_paths)} path(s) queued for scan:\n{listing}")
        if not lines:
            lines.append("Nothing selected yet.")
        self.query_one("#status", Static).update("\n".join(lines))

    def _show_status_error(self, message: str) -> None:
        self.query_one("#status", Static).update(f"[bold #FF5555]{message}[/bold #FF5555]")

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
                self._show_status_error("Pick a file or directory in the tree first.")
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
            self._show_status_error("Pick a file or directory first.")
            return

        severity = self.query_one("#severity-select", Select).value
        lang = self.query_one("#lang-select", Select).value
        check_connect_by = self.query_one("#connect-by-checkbox", Checkbox).value
        verify_mode = self.query_one("#verify-checkbox", Checkbox).value
        baseline_value = self.query_one("#baseline-input", Input).value.strip()
        baseline_path = baseline_value or None

        if verify_mode and baseline_path is None:
            self._show_status_error("Verify mode requires a baseline file.")
            return
        if verify_mode and check_connect_by:
            # Same conflict cli.py's own --verify rejects (see
            # verify_conflict_error): --verify scans generated PostgreSQL
            # output, where a CONNECT BY check against Oracle source
            # doesn't make sense.
            self._show_status_error("Verify mode can't be combined with the CONNECT BY check.")
            return

        if verify_mode:
            self.query_one("#status", Static).update("Verifying...")
            self._run_verify(paths, Path(baseline_path), lang)
        else:
            self.query_one("#status", Static).update("Scanning...")
            self._run_scan(paths, severity, lang, check_connect_by, baseline_path)

    @work(thread=True)
    def _run_scan(
        self,
        paths: list[Path],
        severity: str,
        lang: str,
        check_connect_by: bool,
        baseline_path: str | None,
    ) -> None:
        all_findings, objects_scanned, warnings = scan_paths(
            paths, check_connect_by=check_connect_by, lang=lang
        )
        if lang == "en":
            all_findings = [
                dataclasses.replace(f, message=i18n.translate_message(f.message, "en")) for f in all_findings
            ]

        baseline_diff: BaselineDiff | None = None
        if baseline_path is not None:
            try:
                baseline = load_baseline(Path(baseline_path), lang=lang)
            except BaselineLoadError as exc:
                self.app.call_from_thread(self._show_status_error, f"Couldn't load baseline: {exc}")
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
    def _run_verify(self, paths: list[Path], baseline_path: Path, lang: str) -> None:
        try:
            baseline = load_baseline(baseline_path, lang=lang)
        except BaselineLoadError as exc:
            self.app.call_from_thread(self._show_status_error, f"Couldn't load baseline: {exc}")
            return

        # Same loop cli.py's own _handle_verify() runs, deliberately not
        # shared with scan_paths(): --verify treats `paths` as ora2pg's
        # *generated* PostgreSQL output, not Oracle source, so none of
        # scan_paths()'s Oracle-specific extras (--check-connect-by) apply.
        expanded, empty_dirs = _expand_paths(paths)
        warnings = [f"No .sql/.pks/.pkb files found under {d}" for d in empty_dirs]
        post_migration_findings: list[Finding] = []
        for file_path in expanded:
            if not file_path.is_file():
                warnings.append(f"Not found: {file_path}")
                continue
            try:
                source = file_path.read_text(errors="replace")
            except OSError as exc:
                warnings.append(f"Could not read {file_path}: {exc}")
                continue
            post_migration_findings.extend(
                dataclasses.replace(f, source_file=str(file_path)) for f in scan_source(source)
            )

        results = verify_against_baseline(baseline, post_migration_findings)
        scanned_label = ", ".join(str(p) for p in paths)
        self.app.call_from_thread(
            self.app.push_screen, VerifyResultsScreen(results, warnings, scanned_label)
        )


class ResultsScreen(Screen):
    """Findings from one scan: a summary bar, a table, and a details panel
    that fills in when a row is selected -- same information --explain and
    the terminal report already show (message + GAP-NNN + failure_stage),
    just click-driven instead of read off a static panel. Also offers
    saving this scan's findings as a --save baseline snapshot, and shows a
    NEW/RESOLVED/UNCHANGED summary when the scan was run with a baseline
    file to compare against."""

    BINDINGS = [("escape", "app.pop_screen", "Back")]

    CSS = """
    #summary { height: auto; padding: 1 2; border: round $primary; margin: 1 2; background: $panel; }
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
    #baseline-save-controls { height: auto; padding: 0 2; }
    #baseline-save-controls Input { width: 1fr; margin-right: 2; }
    #save-status { height: auto; padding: 0 3; color: $text-muted; }
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

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self._summary_text(), id="summary")
        table: DataTable = DataTable(id="findings-table", cursor_type="row")
        yield table
        yield Static("Select a row to see the full explanation.", id="detail")
        with Horizontal(id="baseline-save-controls"):
            yield Input(placeholder="Save these findings as a baseline to...", id="save-baseline-input")
            yield Button("Save baseline", id="save-baseline-btn")
        yield Static("", id="save-status")
        yield Button("Back to scan", id="back-btn")
        yield Footer()

    def _summary_text(self) -> str:
        if not self.findings:
            base = f"Scanned {self.scanned_path} — no problematic constructs found."
        else:
            counts = summarize_by_severity(self.findings)
            counts_text = ", ".join(f"{name}: {n}" for name, n in ordered_counts(counts))
            lo, hi = estimate_hours(self.findings)
            base = (
                f"Scanned {self.scanned_path} — objects: {self.objects_scanned}, "
                f"findings: {len(self.findings)} ({counts_text}) — rough estimate {lo:.2f}-{hi:.2f}h "
                f"(uncalibrated heuristic, not a measurement)"
            )
        if self.baseline_diff is not None:
            d = self.baseline_diff
            base += (
                f"\n[bold]Baseline:[/bold] [#FF5555]{len(d.new)} new[/#FF5555], "
                f"[#50FA7B]{len(d.resolved)} resolved[/#50FA7B], {d.unchanged_count} unchanged"
            )
        if self.warnings:
            base += "\n[#F1FA8C]" + " / ".join(self.warnings) + "[/#F1FA8C]"
        return base

    def on_mount(self) -> None:
        table = self.query_one("#findings-table", DataTable)
        # Just the basename, not the full path handed to --tui (usually a
        # long absolute path from the DirectoryTree, repeated on nearly
        # every row of a single-file scan) -- the full path is already in
        # the summary bar above. Without this, File alone can push
        # Detector/GAP off the right edge of the table entirely, hiding
        # the one thing this table exists to surface.
        table.add_columns("Severity", "File", "Object", "Line", "Detector", "GAP")
        for i, f in enumerate(self.findings):
            gap_number, _ = gap_metadata(f.detector)
            table.add_row(
                f"[{_SEVERITY_STYLE.get(f.severity, '')}]{f.severity}[/]",
                Path(f.source_file).name if f.source_file else "—",
                f.object_name,
                str(f.line),
                f.detector,
                f"GAP-{gap_number}" if gap_number else "—",
                key=str(i),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        index = int(event.row_key.value)
        f = self.findings[index]
        gap_number, failure_stage = gap_metadata(f.detector)
        # GAP-NNN/stage comes right after the header, before the message
        # body -- not after it. f.message can run to several wrapped
        # lines (see e.g. bulk_collect's), and #detail has a fixed height
        # with overflow-y: auto -- put the GAP reference last and a long
        # enough message pushes the one thing this panel exists to show
        # (when does this actually break) below the visible area with no
        # obvious indication there's more to scroll to.
        lines = [f"[bold]{f.detector}[/bold] ({f.object_name}:{f.line})"]
        if gap_number is not None:
            ref = f"GAP-{gap_number}"
            if failure_stage is not None:
                # Same short label terminal_report.py's own explanation
                # panel uses -- respects the language picked for this
                # scan, same as f.message already does.
                stage_label = i18n.t(self.lang, f"failure_stage_short_{failure_stage}")
                lines.append(f"[dim]{ref} · {stage_label}[/dim]")
            else:
                lines.append(f"[dim]{ref}[/dim]")
        lines.append("")
        lines.append(f.message)
        self.query_one("#detail", Static).update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back-btn":
            self.app.pop_screen()
            return
        if event.button.id == "save-baseline-btn":
            value = self.query_one("#save-baseline-input", Input).value.strip()
            if not value:
                self.query_one("#save-status", Static).update(
                    "[bold #FF5555]Enter a path first.[/bold #FF5555]"
                )
                return
            try:
                save_baseline(self.all_findings, Path(value))
            except OSError as exc:
                self.query_one("#save-status", Static).update(
                    f"[bold #FF5555]Couldn't save: {exc}[/bold #FF5555]"
                )
                return
            self.query_one("#save-status", Static).update(
                f"[#50FA7B]Saved {len(self.all_findings)} findings to {value}[/#50FA7B]"
            )


class VerifyResultsScreen(Screen):
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

    def __init__(self, results: list[DetectorVerification], warnings: list[str], scanned_path: str) -> None:
        super().__init__()
        self.results = results
        self.warnings = warnings
        self.scanned_path = scanned_path

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self._summary_text(), id="verify-summary")
        yield DataTable(id="verify-table", cursor_type="row")
        yield Static(
            "NOT_DETECTED means the pattern wasn't found in the checked code, not that the "
            "problem is provably fixed. NOT_VERIFIABLE detectors are dropped from ora2pg's own "
            "output on every migration, so re-checking here can't prove anything either way.",
            id="verify-footer-note",
        )
        yield Button("Back to scan", id="verify-back-btn")
        yield Footer()

    def _summary_text(self) -> str:
        counts = {"still_present": 0, "not_detected": 0, "not_verifiable": 0}
        for r in self.results:
            counts[r.status] = counts.get(r.status, 0) + 1
        base = (
            f"Verified {self.scanned_path} against baseline — {len(self.results)} baseline "
            f"detectors: {counts['still_present']} still present, {counts['not_detected']} not "
            f"detected, {counts['not_verifiable']} not verifiable"
        )
        if self.warnings:
            base += "\n[#F1FA8C]" + " / ".join(self.warnings) + "[/#F1FA8C]"
        return base

    def on_mount(self) -> None:
        table = self.query_one("#verify-table", DataTable)
        table.add_columns("Detector", "GAP", "Before", "After", "Status")
        for r in self.results:
            table.add_row(
                r.detector,
                f"GAP-{r.gap_number}" if r.gap_number else "—",
                str(r.baseline_count),
                str(r.post_migration_count) if r.status != "not_verifiable" else "—",
                f"[{_VERIFY_STATUS_STYLE.get(r.status, '')}]{r.status.upper()}[/]",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "verify-back-btn":
            self.app.pop_screen()


class GapReportApp(App):
    """Entry point for `ora2pg-gap-report --tui`. See run_tui() below for
    the actual launch (handles the "textual isn't installed" case one
    level up, in cli.py, before this module is even imported)."""

    TITLE = "ora2pg-gap-report"
    SUB_TITLE = "Oracle -> PostgreSQL migration gap report"
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, start_path: Path | None = None) -> None:
        super().__init__()
        self._start_path = start_path or Path.cwd()
        # Dracula (draculatheme.com) -- one of Textual's own built-in
        # themes, not the library's generic default: high-contrast purple
        # on near-black, the option the project's own maintainer picked
        # after comparing it side by side with five other built-in themes.
        # Severity colors above (_SEVERITY_STYLE) are pulled straight from
        # Dracula's own published accents, not picked independently, so
        # they read as part of the same palette rather than clashing with it.
        self.theme = "dracula"

    def on_mount(self) -> None:
        self.push_screen(ScanScreen(self._start_path))


def run_tui(start_path: Path | None = None) -> None:
    GapReportApp(start_path=start_path).run()
