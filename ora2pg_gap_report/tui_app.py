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

_SEVERITY_STYLE = {"high": "bold red", "medium": "bold yellow", "low": "bold green"}

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
    #tree-label { padding: 1 1 0 1; }
    DirectoryTree { height: 1fr; margin: 0 1; }
    #controls { height: auto; padding: 1; }
    #controls Select { width: 24; margin-right: 2; }
    #status { padding: 0 1 1 1; color: $text-muted; }
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
            self.query_one("#status", Static).update("[bold red]Pick a file or directory first.[/bold red]")
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
    #summary { height: auto; padding: 1; border: solid $primary; margin: 1; }
    #findings-table { height: 1fr; margin: 0 1; }
    #detail { height: 12; border: solid $secondary; margin: 1; padding: 1; overflow-y: auto; }
    #back-btn { margin: 1; }
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
            base += "\n[yellow]" + " / ".join(self.warnings) + "[/yellow]"
        return base

    def on_mount(self) -> None:
        table = self.query_one("#findings-table", DataTable)
        table.add_columns("Severity", "File", "Object", "Line", "Detector", "GAP")
        for i, f in enumerate(self.findings):
            gap_number, _ = gap_metadata(f.detector)
            table.add_row(
                f"[{_SEVERITY_STYLE.get(f.severity, '')}]{f.severity}[/]",
                f.source_file,
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
        lines = [f"[bold]{f.detector}[/bold] ({f.object_name}:{f.line})", "", f.message]
        if gap_number is not None:
            ref = f"GAP-{gap_number}"
            lines.append("")
            if failure_stage is not None:
                # Same short label the terminal report's own explanation
                # panel uses (terminal_report.py) -- respects the language
                # picked for this scan, same as f.message already does.
                stage_label = i18n.t(self.lang, f"failure_stage_short_{failure_stage}")
                lines.append(f"[dim]{ref} · {stage_label}[/dim]")
            else:
                lines.append(f"[dim]{ref}[/dim]")
        self.query_one("#detail", Static).update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back-btn":
            self.app.pop_screen()


class GapReportApp(App):
    """Entry point for `ora2pg-gap-report --tui`. See run_tui() below for
    the actual launch (handles the "textual isn't installed" case one
    level up, in cli.py, before this module is even imported)."""

    TITLE = "ora2pg-gap-report"
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, start_path: Path | None = None) -> None:
        super().__init__()
        self._start_path = start_path or Path.cwd()

    def on_mount(self) -> None:
        self.push_screen(ScanScreen(self._start_path))


def run_tui(start_path: Path | None = None) -> None:
    GapReportApp(start_path=start_path).run()
