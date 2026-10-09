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
saved one, --verify a post-migration PostgreSQL scan against a
pre-migration baseline, and --migrate -- same underlying functions
(baseline.py, verification.py, migrate.py) the CLI uses, just
click-driven.
"""

from __future__ import annotations

import dataclasses
import time
from collections import Counter
from pathlib import Path
from typing import cast

from rich.text import Text
from textual.content import Content
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.theme import Theme
from textual.timer import Timer
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    DirectoryTree,
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
from .effort_estimator import estimate_hours
from .gap_registry import gap_metadata
from .recipes import recipe_for, recipe_url
from .html_report import _version, group_by_gap, source_name, stage_key
from . import messages
from .models import Finding
from .verification import DetectorVerification, NewInOutput, new_in_output, verify_against_baseline

# The palette of Claude Code's own terminal UI, which this app is dressed
# after: a warm near-black ground, one clay-orange accent for what matters
# on screen right now, and soft desaturated hues for everything else. The
# stage colours are the same four hues the HTML and terminal reports give
# the stages, shifted to read on this background; the severities reuse
# them, so red always means "fails", amber "look at it", green "fine".
_ACCENT = "#D97757"
_MUTED = "#8F8B82"
_CODE = "#9ECBFF"
_RED = "#FF6B80"
_AMBER = "#EBB85E"
_GREEN = "#4EBA65"
_SEVERITY_STYLE = {"high": f"bold {_RED}", "medium": f"bold {_AMBER}", "low": f"bold {_GREEN}"}
_STAGE_STYLE = {
    "conversion": "#B1B9F9",
    "deployment": _RED,
    "runtime": _AMBER,
    "semantic": "#5FC4B4",
    "none": _MUTED,
}

_THEME = Theme(
    name="ora2pg-gap-report",
    primary=_ACCENT,
    secondary="#B1B9F9",
    accent=_ACCENT,
    warning=_AMBER,
    error=_RED,
    success=_GREEN,
    foreground="#ECEAE4",
    background="#1D1C1A",
    surface="#262522",
    panel="#2F2E2A",
    dark=True,
    variables={
        "border": _ACCENT,
        "border-blurred": "#4A4843",
        "text-muted": _MUTED,
        "block-cursor-background": "#3B3934",
        "block-cursor-foreground": "#FFFFFF",
        "block-cursor-text-style": "bold",
        "block-cursor-blurred-background": "#302F2B",
        "block-cursor-blurred-foreground": "#ECEAE4",
        "block-hover-background": "#2A2926",
        "input-cursor-background": _ACCENT,
        "input-selection-background": "#D9775755",
        "scrollbar": "#3B3934",
        "scrollbar-hover": "#55524B",
        "scrollbar-active": _ACCENT,
        "scrollbar-background": "#1D1C1A",
        "scrollbar-background-hover": "#1D1C1A",
        "scrollbar-background-active": "#1D1C1A",
        "scrollbar-corner-color": "#1D1C1A",
        "button-color-foreground": "#1D1C1A",
        "button-focus-text-style": "bold",
    },
)

_VERIFY_STATUS_STYLE = {
    "still_present": f"bold {_RED}",
    "not_detected": f"bold {_GREEN}",
    "not_verifiable": _MUTED,
    # Not one of DetectorVerification's three statuses: rows for detectors
    # the baseline never had (the conversion introduced the construct),
    # shown in the same table because they answer the same user question
    # -- "what is wrong with the generated output" -- and a second table
    # on this screen would push the first one off a short terminal.
    "new_in_output": f"bold {_AMBER}",
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


def _hints(lang: str, *keys: str) -> Text:
    """The dim key line at the bottom of every screen, in place of
    Textual's Footer: key in the accent, what it does in grey, the way
    Claude Code shows its own shortcuts under the prompt."""
    text = Text()
    for i, key in enumerate(keys):
        if i:
            text.append("   ")
        label, what = i18n.t(lang, f"tui_hint_{key}").split("|", 1)
        text.append(label, style=f"bold {_ACCENT}")
        text.append(f" {what}", style=_MUTED)
    return text


def _flow(items: list[Text], width: int, indent: str = "  ") -> Text:
    """Lay `items` out in lines no wider than `width`, three spaces apart,
    starting each line with `indent`. Done here rather than left to Rich's
    word wrap, which breaks at any space -- non-breaking ones included --
    and so could strand a stage's dot at the end of one line and its name
    at the start of the next."""
    out = Text(indent)
    used = len(indent)
    for i, item in enumerate(items):
        if i and used + 3 + item.cell_len > width:
            out.append("\n" + indent)
            used = len(indent)
        elif i:
            out.append("   ")
            used += 3
        out.append(item)
        used += item.cell_len
    return out


def _banner(lang: str, path: Path | None = None, roomy: bool = False) -> Text:
    """The welcome box's text, after Claude Code's own: an orange asterisk
    and the name, then what the tool is for, then where it is looking.
    `roomy` puts a blank line between them, as Claude Code does; the
    screen asks for it only when the terminal is tall enough to spare
    the rows (see ScanScreen.on_resize)."""
    gap = "\n\n" if roomy else "\n"
    text = Text()
    text.append("* ", style=f"bold {_ACCENT}")
    text.append("ora2pg-gap-report", style="bold")
    text.append(f"  {_version()}", style=_MUTED)
    text.append(f"{gap}  {i18n.t(lang, 'tui_app_subtitle')}", style=_MUTED)
    if path is not None:
        text.append(f"{gap}  cwd: {path.resolve()}", style=_MUTED)
    return text


class _Tree(DirectoryTree):
    """DirectoryTree without its emoji icons: folders get a plain + / -
    that says whether they are open, files a blank of the same width, and
    colour does the rest (see the directory-tree--* rules in the app CSS)."""

    ICON_NODE = "+ "
    ICON_NODE_EXPANDED = "- "
    ICON_FILE = "  "


class _Check(Checkbox):
    """A checkbox drawn as [x] / [ ] in plain keyboard characters, in
    place of Textual's half-block box: grey brackets, an orange x."""

    @property
    def _button(self) -> Content:
        return Content.assemble(
            ("[", _MUTED),
            ("x" if self.value else " ", f"bold {_ACCENT}"),
            ("]", _MUTED),
        )


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


class _SpinnerStatus:
    """The `#status` line of a screen that runs work in a thread: Claude
    Code's "working" spinner while it runs, a red message if it fails.
    Shared by ScanScreen and MigrateScreen."""

    _spinner: Timer | None = None
    _spinner_message = ""
    _spinner_started = 0.0
    _spinner_frame = 0
    _spinner_lang = "ru"

    def _status(self) -> Static:
        return cast("Screen[None]", self).query_one("#status", Static)

    def _start_spinner(self, message: str, lang: str) -> None:
        """Claude Code's "working" line: a pulsing orange asterisk, what is
        happening, and the seconds so far -- redrawn ten times a second
        until the worker hands over a result or an error."""
        self._stop_spinner()
        self._spinner_message = message
        self._spinner_lang = lang
        self._spinner_started = time.monotonic()
        self._spinner_frame = 0
        self._draw_spinner()
        self._spinner = cast("Screen[None]", self).set_interval(0.1, self._draw_spinner)

    def _stop_spinner(self) -> None:
        if self._spinner is not None:
            self._spinner.stop()
            self._spinner = None

    def _draw_spinner(self) -> None:
        shades = (_ACCENT, "#E38E72", "#EBA58E", "#E38E72")
        shade = shades[self._spinner_frame % len(shades)]
        self._spinner_frame += 1
        lang = self._spinner_lang
        seconds = i18n.number(lang, round(time.monotonic() - self._spinner_started, 1))
        text = Text()
        text.append("* ", style=f"bold {shade}")
        text.append(self._spinner_message, style=shade)
        text.append(f"  {i18n.t(lang, 'tui_elapsed', s=seconds)}", style=_MUTED)
        self._status().update(text)

    def _show_status_error(self, message: str | Text) -> None:
        # Style via Text(..., style=...), not inline markup around an
        # f-string -- `message` can carry an exception's own text (e.g. a
        # baseline load error quoting the bad file's content), which must
        # never be parsed as markup either.
        self._stop_spinner()
        if isinstance(message, str):
            message = Text(message, style=f"bold {_RED}")
        self._status().update(message)


# Screen[T] and App[T] are parameterised by what they *return* when
# dismissed; none of these hand a value back to a caller, so None is
# the accurate parameter rather than a placeholder.
class ScanScreen(_SpinnerStatus, Screen[None]):
    """Landing screen: pick one or more paths in the tree, choose
    severity/language and any optional checks (CONNECT BY, baseline
    comparison, --verify), press Scan."""

    CSS = """
    /* Every control is Textual's one-row compact variant: the screen reads
       as a few quiet lines under the banner, like Claude Code's own prompt,
       instead of a wall of three-row boxes. It also leaves the tree most of
       an 80x24 terminal (the smallest this app targets and what
       App.run_test() gives the tests).
       Select widths are the smallest at which each label still fits on
       one row in both languages ("All severities" is the widest); the
       rows' heights and right edges are pinned by
       test_scan_screen_row_widgets_are_all_the_same_height and
       test_scan_screen_row_fits_an_eighty_column_terminal. */
    #tree-label { padding: 0 2; color: $text-muted; }
    #multi-select-controls, #baseline-controls { margin-top: 1; }
    ScanScreen #banner { margin-top: 0; }
    ScanScreen.-roomy #banner, ScanScreen.-roomy #tree-label { margin-top: 1; }
    #tree { height: 1fr; margin: 0 1; padding: 0 1; }
    #controls, #multi-select-controls, #baseline-controls { height: 1; padding: 0 2; }
    #controls { margin-top: 1; }
    #controls Select, #scan-btn { margin-right: 2; }
    #dialect-select { width: 12; }
    #severity-select { width: 20; }
    #lang-select { width: 13; }
    #multi-select-controls Button { margin-right: 2; }
    #baseline-controls Input { width: 1fr; margin-right: 2; }
    #status { height: auto; max-height: 5; padding: 0 2; margin-top: 1; color: $text-muted; }
    """

    def __init__(self, start_path: Path, lang: str = "ru") -> None:
        super().__init__()
        self._start_path = start_path
        self.lang = lang
        self.selected_path: Path | None = None
        self.selected_paths: list[Path] = []
        self._spinner: Timer | None = None
        self._spinner_message = ""
        self._spinner_started = 0.0
        self._spinner_frame = 0
        self._spinner_lang = lang

    def compose(self) -> ComposeResult:
        yield Static(_banner(self.lang, self._start_path), id="banner")
        yield Label(i18n.t(self.lang, "tui_tree_label"), id="tree-label")
        yield _Tree(str(self._start_path), id="tree")
        with Horizontal(id="controls"):
            yield Select(_dialect_options(), value="oracle", id="dialect-select", allow_blank=False, compact=True)
            yield Select(
                _severity_options(self.lang), value="all", id="severity-select", allow_blank=False, compact=True
            )
            yield Select(_LANG_OPTIONS, value=self.lang, id="lang-select", allow_blank=False, compact=True)
            yield Button(i18n.t(self.lang, "tui_scan_btn"), id="scan-btn", variant="primary", compact=True)
            yield Button(i18n.t(self.lang, "tui_migrate_btn"), id="migrate-btn", compact=True)
        with Horizontal(id="multi-select-controls"):
            yield Button(i18n.t(self.lang, "tui_add_to_selection_btn"), id="add-path-btn", compact=True)
            yield Button(i18n.t(self.lang, "tui_clear_selection_btn"), id="clear-paths-btn", compact=True)
            yield _Check(i18n.t(self.lang, "tui_connect_by_checkbox"), id="connect-by-checkbox", compact=True)
        with Horizontal(id="baseline-controls"):
            yield Input(
                placeholder=i18n.t(self.lang, "tui_baseline_input_placeholder"), id="baseline-input", compact=True
            )
            yield _Check(i18n.t(self.lang, "tui_verify_checkbox"), id="verify-checkbox", compact=True)
        yield Static(i18n.t(self.lang, "tui_status_nothing_selected"), id="status")
        yield Static(_hints(self.lang, "tab", "enter", "quit"), classes="hints")

    def on_resize(self, event: events.Resize) -> None:
        # Air between the rows only when the terminal can spare it; on a
        # short one the rows go to the file tree instead.
        roomy = event.size.height >= 34
        self.set_class(roomy, "-roomy")
        self.query_one("#banner", Static).update(_banner(self.lang, self._start_path, roomy=roomy))

    def on_screen_resume(self) -> None:
        # Back from a results screen: the spinner that was running when it
        # opened is stale, and the status line should say what is picked.
        if self._spinner is not None:
            self._stop_spinner()
            self._update_status()

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

        if button_id not in ("scan-btn", "migrate-btn"):
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
        if button_id == "migrate-btn":
            # --migrate's own settings live on its screen; this one only
            # hands over what to migrate, from which dialect, in which
            # language.
            self.app.push_screen(MigrateScreen(paths, dialect, lang, self._start_path))
            return
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
            self._start_spinner(i18n.t(lang, "tui_status_verifying"), lang)
            self._run_verify(paths, Path(baseline_path), lang, dialect)
        else:
            self._start_spinner(i18n.t(lang, "tui_status_scanning"), lang)
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


class MigrateScreen(_SpinnerStatus, Screen[None]):
    """--migrate inside the TUI: where to write, which ora2pg, whether to
    load the result into PostgreSQL in docker -- then the same run
    (migrate.run_migration, migrate.load_and_record) and the same summary
    (terminal_report.render_migration) the command line gives, with the
    steps on the status line while it runs."""

    BINDINGS = [("escape", "back", "Back")]

    CSS = """
    #migrate-intro { color: $text-muted; }
    .migrate-row { height: 1; padding: 0 2; margin-top: 1; }
    .migrate-row Label { width: 11; color: $text-muted; }
    .migrate-row Input { width: 1fr; }
    #migrate-run-btn { margin-left: 2; margin-right: 2; }
    #status { height: auto; max-height: 3; padding: 0 2; margin-top: 1; color: $text-muted; }
    #migrate-result { height: 1fr; margin: 1 1 0 1; padding: 0 1; border: round #4A4843; }
    """

    def __init__(self, paths: list[Path], dialect: str, lang: str, start_path: Path) -> None:
        super().__init__()
        self.paths = paths
        self.dialect = dialect
        self.lang = lang
        self._start_path = start_path
        self.result_text: Text | None = None
        self.running = False

    def compose(self) -> ComposeResult:
        sources = ", ".join(str(p) for p in self.paths)
        intro = Static(Text(i18n.t(self.lang, "tui_migrate_intro", path=sources)), id="migrate-intro", classes="box")
        intro.border_title = f"ora2pg-gap-report  {i18n.t(self.lang, 'tui_migrate_title')}"
        yield intro
        with Horizontal(classes="migrate-row"):
            yield Label(i18n.t(self.lang, "tui_migrate_out_label"))
            yield Input(str(self._default_out()), id="migrate-out", compact=True)
        with Horizontal(classes="migrate-row"):
            yield Label(i18n.t(self.lang, "tui_migrate_ora2pg_label"))
            yield Input(
                "ora2pg",
                placeholder=i18n.t(self.lang, "tui_migrate_ora2pg_placeholder"),
                id="migrate-ora2pg",
                compact=True,
            )
        with Horizontal(classes="migrate-row"):
            yield _Check(i18n.t(self.lang, "tui_migrate_load_checkbox"), id="migrate-load", compact=True)
            yield Button(i18n.t(self.lang, "tui_migrate_run_btn"), id="migrate-run-btn", variant="primary", compact=True)
            yield Button(i18n.t(self.lang, "tui_back_to_scan_btn"), id="migrate-back-btn", compact=True)
        yield Static("", id="status")
        yield Static("", id="migrate-result")
        yield Static(_hints(self.lang, "tab", "enter", "back", "quit"), classes="hints")

    def action_back(self) -> None:
        # Not while a run is going: its worker reports back to this screen.
        if not self.running:
            self.app.pop_screen()

    def _set_running(self, running: bool) -> None:
        self.running = running
        self.query_one("#migrate-run-btn", Button).disabled = running
        self.query_one("#migrate-back-btn", Button).disabled = running

    def _show_status_error(self, message: str | Text) -> None:
        self._set_running(False)
        self._status().display = True
        super()._show_status_error(message)

    def _default_out(self) -> Path:
        """Next to what is migrated, never inside it: schema/ ->
        schema-migration/, schema.sql -> schema-migration/."""
        first = self.paths[0]
        name = first.stem if first.is_file() else first.name
        return first.parent / f"{name or 'ora2pg'}-migration"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "migrate-back-btn":
            self.action_back()
            return
        if event.button.id != "migrate-run-btn":
            return
        out = self.query_one("#migrate-out", Input).value.strip()
        if not out:
            self._show_status_error(i18n.t(self.lang, "tui_migrate_needs_out"))
            return
        ora2pg_bin = self.query_one("#migrate-ora2pg", Input).value.strip() or "ora2pg"
        load = self.query_one("#migrate-load", Checkbox).value
        self.query_one("#migrate-result", Static).update("")
        self.result_text = None
        self._set_running(True)
        self._status().display = True
        self._start_spinner(i18n.t(self.lang, "tui_migrate_running"), self.lang)
        self._run(Path(out).expanduser(), ora2pg_bin, load)

    def _progress(self, key: str) -> None:
        name, _, detail = key.partition(":")
        self._spinner_message = i18n.t(self.lang, name, detail=detail)

    def _show_result(self, text: Text) -> None:
        self._set_running(False)
        self._stop_spinner()
        self._status().update("")
        # The summary says how it went; an empty status line above it
        # would only push it down.
        self._status().display = False
        self.result_text = text
        self.query_one("#migrate-result", Static).update(text)

    @work(thread=True)
    def _run(self, out: Path, ora2pg_bin: str, load_check: bool) -> None:
        # Same outer boundary as ScanScreen._run_scan: an exception escaping
        # a thread worker would take the whole app down.
        try:
            self._run_impl(out, ora2pg_bin, load_check)
        except Exception as exc:
            self.app.call_from_thread(
                self._show_status_error,
                i18n.t(self.lang, "tui_worker_crashed", exc_type=type(exc).__name__, exc=exc),
            )

    def _run_impl(self, out: Path, ora2pg_bin: str, load_check: bool) -> None:
        import io

        from rich.console import Console
        from rich.markup import escape

        from .load_check import LoadCheckError
        from .migrate import MigrateError, load_and_record, run_migration
        from .ora2pg_wrapper import Ora2PgNotFoundError, Ora2PgRunError
        from .terminal_report import render_migration

        lang = self.lang

        def fail(markup: str, plain: str = "") -> None:
            message = Text(plain, style=f"bold {_RED}") if plain else Text()
            if plain:
                message.append("\n")
            message.append(Text.from_markup(markup))
            self.app.call_from_thread(self._show_status_error, message)

        sources, _ = expand_paths(self.paths)
        sources = [p for p in sources if p.is_file()]
        if not sources:
            fail(i18n.t(lang, "no_paths_error"))
            return
        try:
            result = run_migration(
                sources,
                out,
                dialect=self.dialect,
                ora2pg_bin=ora2pg_bin,
                lang=lang,
                version=_version(),
                progress=lambda key: self.app.call_from_thread(self._progress, key),
            )
            load = None
            if load_check and result.converted:
                self.app.call_from_thread(self._progress, "migrate_step_load")
                load = load_and_record(result, "docker", dialect=self.dialect, lang=lang)
        except (MigrateError, LoadCheckError) as exc:
            fail(i18n.t(lang, exc.key, **{k: escape(str(v)) for k, v in exc.kwargs.items()}))
            return
        except (Ora2PgNotFoundError, Ora2PgRunError) as exc:
            fail(i18n.t(lang, "migrate_ora2pg_hint"), plain=str(exc))
            return

        width = max(60, self.size.width - 6)
        console = Console(file=io.StringIO(), record=True, width=width, force_terminal=True, color_system="truecolor")
        render_migration(result, load, console=console, lang=lang, load_check_asked=load_check, in_tui=True)
        self.app.call_from_thread(self._show_result, Text.from_ansi(console.export_text(styles=True).lstrip("\n")))


class ResultsScreen(Screen[None]):
    """Findings from one scan: a summary bar, a table, and a details panel
    that fills in when a row is selected -- same information --explain and
    the terminal report already show (message + GAP-NNN + failure_stage),
    just click-driven instead of read off a static panel. Also offers
    saving this scan's findings as a --save baseline snapshot, and shows a
    NEW/RESOLVED/UNCHANGED summary when the scan was run with a baseline
    file to compare against."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        # The arrows belong to the table; the explanation under it can be
        # longer than its box, so it scrolls on its own keys.
        # priority: the table has page keys of its own and would take them.
        Binding("pagedown", "scroll_detail(1)", "Scroll the explanation", priority=True),
        Binding("pageup", "scroll_detail(-1)", "Scroll the explanation", priority=True),
    ]

    CSS = """
    /* The summary is capped at 7 rows (5 lines inside the border) and
       scrolls past that: the scanned path's length depends on where the
       repo is checked out, and an uncapped box once wrapped one line
       taller on CI than locally and pushed #back-btn below the 80x24
       viewport the tests use. */
    #summary { max-height: 8; overflow-y: auto; }
    /* Proportional heights, not a fixed one for #detail: a fixed 14 rows
       pushed #back-btn off an 80x24 terminal. The table gets more room,
       the detail box enough for gap, stage, place and what to do. */
    #findings-table { height: 3fr; margin: 0 1; }
    #detail-box { height: 2fr; margin: 0 1; padding: 0 1; }
    #detail { height: auto; }
    /* Save and Back share one compact row: two rows of buttons were what
       squeezed the detail box to nothing on a 24-line terminal. */
    #baseline-save-controls { height: 1; padding: 0 2; margin-top: 1; }
    #baseline-save-controls Input { width: 1fr; margin-right: 2; }
    #baseline-save-controls Button { margin-right: 2; }
    #back-btn { margin: 0; }
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
        # In the order the reports list gaps -- by the stage a migration
        # reaches first -- so one gap's rows sit together in the table.
        self.findings = [f for group in group_by_gap(findings) for f in group.findings]
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
        # Width the summary's items are laid out for; on_resize keeps it
        # current.
        self._width = 72
        # Set by the "Save baseline" button, folded into #summary instead of
        # its own row -- a screen already tight enough at 80x24 to have
        # pushed #back-btn out of the visible viewport once (see the CSS
        # comment on #detail below) doesn't have a spare row for it. A
        # Text, not a markup string: it carries a user-typed path or an
        # OSError's own text, neither safe to run through markup parsing.
        self._save_status: Text | None = None

    def compose(self) -> ComposeResult:
        summary = Static(self._summary_text(), id="summary", classes="box")
        summary.border_title = "ora2pg-gap-report"
        yield summary
        table: DataTable[str] = DataTable(id="findings-table", cursor_type="row", zebra_stripes=False)
        table.border_title = i18n.count(self.lang, "finding", len(self.findings))
        yield table
        # A scroll container around the text: a Static alone clips a long
        # explanation to its box, with no way to read the rest.
        with VerticalScroll(id="detail-box"):
            yield Static(Text(i18n.t(self.lang, "tui_results_select_row_hint"), style=_MUTED), id="detail")
        with Horizontal(id="baseline-save-controls"):
            yield Input(
                placeholder=i18n.t(self.lang, "tui_save_baseline_input_placeholder"),
                id="save-baseline-input",
                compact=True,
            )
            yield Button(i18n.t(self.lang, "tui_save_baseline_btn"), id="save-baseline-btn", compact=True)
            yield Button(i18n.t(self.lang, "tui_back_to_scan_btn"), id="back-btn", compact=True)
        yield Static(_hints(self.lang, "move", "page", "back", "quit"), classes="hints")

    def on_resize(self, event: events.Resize) -> None:
        # The summary's items are laid out by hand for the current width
        # (see _flow), so a resize lays them out again.
        self._width = max(event.size.width - 8, 20)
        self.query_one("#summary", Static).update(self._summary_text())

    def _summary_text(self) -> Text:
        # Built as a Text, appended to piece by piece, not as an f-string
        # with inline [style] markup: scanned_path and warnings carry
        # scanned-content/filesystem text verbatim (a path with brackets
        # would raise MarkupError on Static.update() otherwise).
        if not self.findings:
            text = Text(i18n.t(self.lang, "tui_scanned_no_findings", path=self.scanned_path))
        else:
            lang = self.lang
            gaps = group_by_gap(self.findings)
            text = Text()
            text.append("* ", style=f"bold {_ACCENT}")
            text.append(i18n.t(lang, "report_heading", source=source_name(self.findings)) + "\n", style="bold")
            per_stage = Counter(stage_key(g.stage) for g in gaps for _ in g.findings)
            stages: list[Text] = []
            for key in ("conversion", "deployment", "runtime", "semantic", "none"):
                n = per_stage.get(key, 0)
                if not n and key == "none":
                    continue
                style = _STAGE_STYLE[key] if n else "#55524B"
                item = Text()
                item.append("● ", style=style)
                item.append(f"{i18n.t(lang, f'stage_{key}_name')} ", style=_MUTED if not n else "")
                item.append(str(n), style=f"bold {style}" if n else _MUTED)
                stages.append(item)
            text.append(_flow(stages, self._width))
            text.append("\n")
            lo, hi = estimate_hours(self.findings)
            found = Text(
                i18n.t(
                    lang,
                    "report_found",
                    findings=i18n.count(lang, "finding", len(self.findings)),
                    gaps=i18n.count(lang, "gap", len(gaps)),
                )
            )
            effort = Text(f"{i18n.t(lang, 'effort_panel_title')}: ", style=_MUTED)
            effort.append(
                i18n.t(lang, "report_effort_range", lo=i18n.hours(lang, lo), hi=i18n.hours(lang, hi)),
                style="bold",
            )
            effort.append(f" {i18n.t(lang, 'tui_effort_caveat')}", style=_MUTED)
            text.append(_flow([found, effort], self._width))
            text.append("\n")
            text.append("  " + i18n.t(lang, "tui_scanned_path", path=self.scanned_path), style=_MUTED)
        if self.baseline_diff is not None:
            # NEW/RESOLVED/UNCHANGED stay untranslated words here, same as
            # terminal_report.py's own render_baseline_diff() -- fixed
            # status vocabulary, not prose (see _severity_options()'s own
            # reasoning for the same choice with high/medium/low).
            d = self.baseline_diff
            text.append("\n  ")
            text.append("Baseline: ", style="bold")
            text.append(f"{len(d.new)} new", style=_RED)
            text.append(", ")
            text.append(f"{len(d.resolved)} resolved", style=_GREEN)
            text.append(f", {d.unchanged_count} unchanged")
        if self.warnings:
            text.append("\n  ")
            text.append(" / ".join(self.warnings), style=_AMBER)
        if self._save_status is not None:
            text.append("\n  ")
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
            i18n.t(self.lang, "report_filter_stage"),
            "GAP",
            i18n.t(self.lang, "col_object"),
            i18n.t(self.lang, "col_line"),
            i18n.t(self.lang, "col_file"),
        )
        for i, f in enumerate(self.findings):
            gap_number, failure_stage = gap_metadata(f.detector)
            key = stage_key(failure_stage)
            # Text(...) per cell, not markup strings: object_name/file name
            # come straight from the scanned source (a quoted identifier
            # like "my[table]" would otherwise be parsed as a style tag).
            table.add_row(
                Text(f.severity, style=_SEVERITY_STYLE.get(f.severity, "")),
                Text(i18n.t(self.lang, f"stage_{key}_name"), style=_STAGE_STYLE[key]),
                Text(f"GAP-{gap_number}" if gap_number else "—"),
                Text(f.object_name),
                Text(str(f.line)),
                Text(Path(f.source_file).name if f.source_file else "—", style=_MUTED),
                key=str(i),
            )

    def action_scroll_detail(self, direction: int) -> None:
        detail = self.query_one("#detail-box", VerticalScroll)
        if direction > 0:
            detail.scroll_page_down(animate=False)
        else:
            detail.scroll_page_up(animate=False)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # The detail box follows the cursor, so arrowing down the table
        # reads through the findings without pressing Enter on each one.
        self._show_detail(event.row_key.value)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._show_detail(event.row_key.value)

    def _show_detail(self, row_key_value: str | None) -> None:
        assert row_key_value is not None  # every row is added with key=str(i) in on_mount()
        f = self.findings[int(row_key_value)]
        gap_number, failure_stage = gap_metadata(f.detector)
        lang = self.lang
        key = stage_key(failure_stage)
        # What to act on first, while it is still on screen: the gap, when
        # it breaks, where, and what to do. The explanation -- several
        # wrapped lines -- goes last, where scrolling to it costs nothing.
        # Built as a Text, piece by piece: object names, snippets and paths
        # come from the scanned source and must never be parsed as markup
        # (a quoted identifier like "my[table]" would raise MarkupError).
        text = Text()
        if gap_number is not None:
            text.append(f"GAP-{gap_number}  ", style=f"bold {_STAGE_STYLE[key]}")
        text.append(messages.title(f.detector, lang).replace("`", ""), style="bold")
        text.append("\n")
        if failure_stage is not None:
            text.append(
                f"{i18n.t(lang, 'report_rail_label')}: "
                f"{i18n.t(lang, f'failure_stage_short_{failure_stage}')} - {i18n.t(lang, f'stage_{key}_desc')}",
                style=_STAGE_STYLE[key],
            )
            text.append("\n")
        text.append("\n")
        text.append(f"{f.object_name}:{f.line}", style="bold")
        text.append(f"  {f.source_file}" if f.source_file else "", style=_MUTED)
        text.append("\n")
        text.append("  ")
        text.append(f.snippet, style=_CODE)
        hint = messages.remediation_hint(f.detector, lang)
        if hint:
            text.append(f"\n\n{i18n.t(lang, 'report_gap_fix')}  ", style=f"bold {_ACCENT}")
            text.append(hint)
        recipe = recipe_for(f.detector)
        if recipe is not None:
            url = recipe_url(recipe, lang)
            text.append(f"\n{i18n.t(lang, 'report_gap_recipe')}  ", style=f"bold {_ACCENT}")
            text.append(recipe.title(lang), style=f"link {url}")
            text.append(f"\n{url}", style=_MUTED)
        text.append(f"\n\n{i18n.t(lang, 'report_gap_why')}  ", style=f"bold {_MUTED}")
        text.append(messages.text(f.message_id, lang), style="#CFCBC2")
        box = self.query_one("#detail-box", VerticalScroll)
        # The box takes the colour of the stage the finding breaks at, the
        # same hue its row carries in the table's Stage column.
        box.styles.border = ("round", _STAGE_STYLE[key])
        box.border_title = i18n.t(lang, f"stage_{key}_name")
        box.scroll_home(animate=False)
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
                    i18n.t(self.lang, "tui_error_enter_path_first"), style=f"bold {_RED}"
                )
            else:
                try:
                    save_baseline(self.all_findings, Path(value))
                except OSError as exc:
                    self._save_status = Text(
                        i18n.t(self.lang, "tui_error_couldnt_save", exc=exc), style=f"bold {_RED}"
                    )
                else:
                    self._save_status = Text(
                        i18n.t(self.lang, "tui_saved_findings", n=len(self.all_findings), path=value),
                        style=_GREEN,
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
    #verify-table { height: 1fr; margin: 0 1; }
    #verify-footer-note { height: auto; padding: 0 2; margin-top: 1; color: $text-muted; }
    #verify-back-btn { margin: 1 2 0 2; }
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
        summary = Static(self._summary_text(), id="verify-summary", classes="box")
        summary.border_title = "ora2pg-gap-report"
        yield summary
        yield DataTable(id="verify-table", cursor_type="row")
        # Same footer disclaimer text as terminal_report.py's own
        # render_verification() -- reuses its i18n key rather than a
        # tui_-prefixed duplicate.
        yield Static(i18n.t(self.lang, "verify_footer_note"), id="verify-footer-note")
        yield Button(i18n.t(self.lang, "tui_back_to_scan_btn"), id="verify-back-btn", compact=True)
        yield Static(_hints(self.lang, "move", "back", "quit"), classes="hints")

    def _summary_text(self) -> Text:
        # Text(...), not an f-string with inline markup: scanned_path and
        # warnings carry scanned-path/filesystem text verbatim -- same
        # reasoning as ResultsScreen._summary_text().
        counts = {"still_present": 0, "not_detected": 0, "not_verifiable": 0}
        for r in self.results:
            counts[r.status] = counts.get(r.status, 0) + 1
        text = Text("* ", style=f"bold {_ACCENT}")
        text.append(
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
            text.append("\n  ")
            text.append(" / ".join(self.warnings), style=_AMBER)
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

    # Shared by every screen: the look is Claude Code's -- no header bar,
    # no filled panels, thin rounded borders, orange only on what has
    # focus or matters most, grey for everything that is just context.
    CSS = """
    Screen { background: $background; }
    #banner {
        width: auto; max-width: 100%; height: auto;
        border: round $primary; padding: 0 2 0 1; margin: 1 1 0 1;
    }
    .box {
        height: auto; border: round $primary; padding: 0 1; margin: 1 1 0 1;
        border-title-color: $text-muted; border-title-style: none;
    }
    .hints { height: 1; padding: 0 2; margin-top: 1; }

    DirectoryTree, DataTable, #detail-box {
        background: $background; border: round #4A4843;
        border-title-color: $text-muted; border-title-style: none;
    }
    DirectoryTree:focus, DataTable:focus { border: round $primary; background-tint: $foreground 0%; }
    DirectoryTree, DataTable, #detail-box { scrollbar-size: 0 1; }
    DirectoryTree > .directory-tree--folder { color: $primary; text-style: bold; }
    DirectoryTree > .directory-tree--extension { color: $text-muted; text-style: none; }
    DirectoryTree > .directory-tree--file { color: $foreground; }
    DirectoryTree > .tree--guides { color: #4A4843; }
    DirectoryTree > .tree--guides-hover { color: #6B675F; }
    DirectoryTree > .tree--guides-selected { color: $primary; }

    DataTable > .datatable--header { background: $background; color: $text-muted; text-style: bold; }
    DataTable > .datatable--even-row, DataTable > .datatable--odd-row { background: $background; }
    DataTable > .datatable--hover { background: #2A2926; }

    Button {
        background: $panel; color: $foreground; text-style: none;
        padding: 0 1; min-width: 0;
    }
    Button:hover { background: #3B3934; }
    Button:focus { background: #3B3934; color: $primary; text-style: bold; }
    Button.-primary { background: $primary; color: #1D1C1A; text-style: bold; }
    Button.-primary:hover { background: #E38E72; }
    Button.-primary:focus { background: #EBA58E; color: #1D1C1A; }

    Select > SelectCurrent { background: $panel; }
    Select:focus > SelectCurrent { background: #3B3934; }
    Select > SelectCurrent .arrow { color: $primary; }
    Input { background: $panel; }
    Input:focus { background: #3B3934; }
    Input > .input--placeholder { color: #6B675F; }
    Checkbox { background: $background; }
    Checkbox:focus { background-tint: $foreground 0%; }
    Checkbox:focus > .toggle--label { color: $primary; background: $background; text-style: bold; }
    """

    def __init__(self, start_path: Path | None = None, lang: str = "ru") -> None:
        super().__init__()
        self._start_path = start_path or Path.cwd()
        self.lang = lang
        self.sub_title = i18n.t(lang, "tui_app_subtitle")
        # A theme of this app's own (see _THEME above) rather than one of
        # Textual's built-ins, so the widgets' own colours -- focus rings,
        # cursors, scrollbars -- come from the same palette as the text.
        self.register_theme(_THEME)
        self.theme = _THEME.name

    def on_mount(self) -> None:
        self.push_screen(ScanScreen(self._start_path, self.lang))


def run_tui(start_path: Path | None = None, lang: str = "ru") -> None:
    GapReportApp(start_path=start_path, lang=lang).run()
