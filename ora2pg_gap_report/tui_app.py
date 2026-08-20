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

Deliberately not attempted in this first version -- not because they're
hard, because they're a second slice, not proof the first one earns its
keep yet (same "start small, expand only once it's validated" reasoning
ROADMAP.md already applies to failure_stage): --save/--baseline/--verify
from inside the TUI, --check-connect-by, multi-path selection (one file or
one directory at a time, picked from the tree). All of those stay a normal
CLI invocation for now.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, DirectoryTree, Footer, Header, Label, Select, Static

from . import i18n
from .cli import _expand_paths, count_objects, scan_source
from .cli import _sort_findings as sort_findings
from .effort_estimator import estimate_hours, ordered_counts, summarize_by_severity
from .gap_registry import gap_metadata
from .models import Finding

# Nord's own aurora accent colors (nordtheme.com/docs/colors-and-palettes)
# for error/warning/success -- not the plain named "red"/"yellow"/"green"
# Rich would otherwise pick, which look harsh and don't match the app's
# Nord theme (see GapReportApp.theme below) at all. Nord ships as one of
# Textual's own built-in themes, already tuned for contrast on a dark
# background -- picking a maintained, tested palette here beats hand-
# rolling colors and hoping they read well.
_SEVERITY_STYLE = {"high": "bold #BF616A", "medium": "bold #EBCB8B", "low": "bold #A3BE8C"}

_SEVERITY_OPTIONS = [("All severities", "all"), ("High only", "high"), ("Medium only", "medium"), ("Low only", "low")]
_LANG_OPTIONS = [("Russian output", "ru"), ("English output", "en")]


def scan_path(path: Path) -> tuple[list[Finding], int, list[str]]:
    """One file or one directory in, findings out -- the same read ->
    scan_source() -> stamp source_file -> count_objects() sequence cli.py's
    own main() runs per path, just not sharing that loop directly (it's
    entangled with argparse's Namespace and --check-connect-by, neither of
    which applies here yet). Returns (findings, objects_scanned, warnings)
    instead of printing anything -- this module has no opinion on how a
    caller shows a warning, unlike cli.py's err_console.print() calls."""
    findings: list[Finding] = []
    objects_scanned = 0
    warnings: list[str] = []

    expanded, empty_dirs = _expand_paths([path])
    for empty_dir in empty_dirs:
        warnings.append(f"No .sql/.pks/.pkb files found under {empty_dir}")

    for file_path in expanded:
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

    sort_findings(findings)
    return findings, objects_scanned, warnings


class ScanScreen(Screen):
    """Landing screen: pick a path in the tree, choose severity/language,
    press Scan (or Enter on the button)."""

    CSS = """
    #tree-label { padding: 1 2 0 2; color: $text-muted; text-style: italic; }
    DirectoryTree { height: 1fr; margin: 1 2; border: round $panel-lighten-1; padding: 1; }
    #controls { height: auto; padding: 1 2; }
    #controls Select { width: 26; margin-right: 2; }
    #controls Button { margin-top: 0; }
    #status { height: auto; padding: 0 3 1 3; color: $text-muted; }
    """

    def __init__(self, start_path: Path) -> None:
        super().__init__()
        self._start_path = start_path
        self.selected_path: Path | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Pick a .sql/.pks/.pkb file, or a directory to scan recursively:", id="tree-label")
        yield DirectoryTree(str(self._start_path), id="tree")
        with Horizontal(id="controls"):
            yield Select(_SEVERITY_OPTIONS, value="all", id="severity-select", allow_blank=False)
            yield Select(_LANG_OPTIONS, value="ru", id="lang-select", allow_blank=False)
            yield Button("Scan", id="scan-btn", variant="primary")
        yield Static("Nothing selected yet.", id="status")
        yield Footer()

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self.selected_path = event.path
        self.query_one("#status", Static).update(f"Selected file: {event.path}")

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self.selected_path = event.path
        self.query_one("#status", Static).update(f"Selected directory: {event.path} (scanned recursively)")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "scan-btn":
            return
        if self.selected_path is None:
            self.query_one("#status", Static).update("[bold #BF616A]Pick a file or directory first.[/bold #BF616A]")
            return
        severity = self.query_one("#severity-select", Select).value
        lang = self.query_one("#lang-select", Select).value
        self.query_one("#status", Static).update("Scanning...")
        self._run_scan(self.selected_path, severity, lang)

    @work(thread=True)
    def _run_scan(self, path: Path, severity: str, lang: str) -> None:
        findings, objects_scanned, warnings = scan_path(path)
        if severity != "all":
            findings = [f for f in findings if f.severity == severity]
        if lang == "en":
            findings = [
                dataclasses.replace(f, message=i18n.translate_message(f.message, "en")) for f in findings
            ]
        self.app.call_from_thread(
            self.app.push_screen, ResultsScreen(findings, objects_scanned, warnings, lang, str(path))
        )


class ResultsScreen(Screen):
    """Findings from one scan: a summary bar, a table, and a details panel
    that fills in when a row is selected -- same information --explain and
    the terminal report already show (message + GAP-NNN + failure_stage),
    just click-driven instead of read off a static panel."""

    BINDINGS = [("escape", "app.pop_screen", "Back")]

    CSS = """
    #summary { height: auto; padding: 1 2; border: round $primary; margin: 1 2; background: $panel; }
    /* 2fr/1fr, not a fixed height for #detail: a fixed height (tried
       first at 14) doesn't scale down on a small terminal -- at the
       80x24 Textual itself defaults to for headless/test runs, the rest
       of this screen's fixed-height chrome (header, summary, back
       button, footer) plus a 14-row detail box genuinely doesn't fit,
       pushing #back-btn below the visible viewport entirely. Sharing
       the remaining space proportionally guarantees both boxes fit
       whatever the real terminal size is, just with different
       proportions. */
    #findings-table { height: 2fr; margin: 0 2; border: round $panel-lighten-1; }
    #detail {
        height: 1fr; border: round $accent; margin: 1 2; padding: 1 2;
        overflow-y: auto; background: $panel;
    }
    #back-btn { margin: 0 2 1 2; }
    """

    def __init__(
        self, findings: list[Finding], objects_scanned: int, warnings: list[str], lang: str, scanned_path: str
    ) -> None:
        super().__init__()
        self.findings = findings
        self.objects_scanned = objects_scanned
        self.warnings = warnings
        self.lang = lang
        self.scanned_path = scanned_path

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self._summary_text(), id="summary")
        table: DataTable = DataTable(id="findings-table", cursor_type="row")
        yield table
        yield Static("Select a row to see the full explanation.", id="detail")
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
        if self.warnings:
            base += "\n[#EBCB8B]" + " / ".join(self.warnings) + "[/#EBCB8B]"
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
        # Nord (nordtheme.com) -- one of Textual's own built-in themes, not
        # the library's generic default: cool, muted, high-contrast on a
        # dark background, the kind of palette this project's audience
        # (terminal-first DBAs/devs) already tends to reach for. Severity
        # colors above (_SEVERITY_STYLE) are pulled straight from Nord's
        # own published aurora accents, not picked independently, so they
        # read as part of the same palette rather than clashing with it.
        self.theme = "nord"

    def on_mount(self) -> None:
        self.push_screen(ScanScreen(self._start_path))


def run_tui(start_path: Path | None = None) -> None:
    GapReportApp(start_path=start_path).run()
