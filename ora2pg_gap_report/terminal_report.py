"""Rich-based terminal rendering — presentation only.

Deliberately its own module, not folded into report_generator.py: the
detector library (models.py, detectors/, report_generator.py) stays
importable with zero dependencies; only the CLI's interactive terminal
output pulls in `rich`. report_generator.py's plain JSON/Markdown stay
the machine-readable / redirect-to-a-file formats.

The report follows the HTML one (html_report.py), whose GapGroup model
it shares: the failure stages first, then each gap once, then each gap
in detail with its explanation printed once and only its first few
occurrences -- a terminal is no place for a 389-row table, and every
other format carries the full list.

Deliberately NOT here: a single "migration readiness" score, a risk
level (LOW/MEDIUM/HIGH/...), per-category "compatibility %" numbers, or
an auto-detected Oracle version. Those would need a scoring methodology
this project doesn't have and hasn't calibrated against real migrations
— showing a confident-looking number with no real basis behind it is
exactly the overclaiming this project's own effort estimate deliberately
avoids (see effort_estimator.py's docstring). Only counts and ranges
genuinely computed from the findings appear here, and the effort
estimate is shown as the range it is, never collapsed to a midpoint.
"""

from collections import Counter
from pathlib import Path
from collections.abc import Callable
from typing import TYPE_CHECKING

from rich.console import Console, Group, RenderableType
from rich.markup import escape
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import i18n
from .baseline import BaselineDiff
from .effort_estimator import (
    distinct_detector_count,
    estimate_hours,
    ordered_counts,
    summarize_by_severity,
)
from .gap_registry import gap_by_detector, gap_metadata
from .load_check import CATEGORIES, FAILING_CATEGORIES, LoadCheckResult, LoadError
from .html_report import source_dialect
from .html_report import STAGES, GapGroup, group_by_gap, source_name, stage_key
from .models import Finding
from .prepare import prepare_command

if TYPE_CHECKING:
    from .migrate import MigrationResult
from .recipes import Recipe, recipe_for, recipe_url
from . import messages
from .verification import DetectorVerification, NewInOutput

# Mid-tones of the TUI's and the HTML report's palette: dark enough to
# read on a light terminal, light enough on a dark one.
_SEVERITY_STYLE = {
    "high": "bold #E5484D",
    "medium": "bold #D9A21B",
    "low": "bold #46A758",
}
# The one accent, Claude Code's clay orange, kept for the report's mark and
# the snippets it quotes from your source; code named in titles and hints
# gets a quieter blue, so the orange stays rare enough to mean something.
_ACCENT = "#D97757"
_TOP_OBJECTS_LIMIT = 10
# How many occurrences of one gap the terminal lists before pointing at
# the formats that carry all of them.
_OCCURRENCES_SHOWN = 5
# The stage colours of the HTML report, as close as a terminal gets.
_STAGE_STYLE = {
    "conversion": "#8b6cf0",
    "deployment": "#e5484d",
    "runtime": "#D9A21B",
    "semantic": "#12a594",
    "none": "grey62",
}
_CODE_STYLE = "#5B8DEF"



def _severity_dot(severity: str | None) -> str:
    """'●' for a known severity, '○' for anything else (an unrecognized
    value like effort_estimator's "other" bucket, or no severity at all)."""
    return "●" if severity in _SEVERITY_STYLE else "○"


def _worst_severity(severities: set[str]) -> str | None:
    for sev in ("high", "medium", "low"):
        if sev in severities:
            return sev
    return next(iter(severities), None)


def render(
    findings: list[Finding],
    console: Console | None = None,
    elapsed_seconds: float | None = None,
    objects_scanned: int | None = None,
    lang: str = "ru",
) -> None:
    """The interactive report, in the same order as the HTML one: where the
    gaps break the migration, how serious and how costly, each gap once,
    then each gap in detail with its first few occurrences.

    Every piece of scanned content -- object names, paths, snippets -- goes
    through Text(), never through Rich markup: a path like
    "notes[/archive].sql" would otherwise raise MarkupError, and a snippet
    like "arr[red]" would lose what looks like a style tag."""
    console = console or Console()

    if not findings:
        empty_message = Text(i18n.t(lang, "no_findings"))
        if objects_scanned is not None:
            empty_message.append(i18n.t(lang, "objects_scanned_inline", n=objects_scanned))
        if elapsed_seconds is not None:
            empty_message.append(i18n.t(lang, "elapsed_inline", s=i18n.number(lang, round(elapsed_seconds, 1))), style="dim")
        console.print(Panel(empty_message, border_style="#46A758"))
        return

    gaps = group_by_gap(findings)
    _render_heading(console, findings, gaps, objects_scanned, elapsed_seconds, lang)
    _render_rail(console, gaps, lang)
    _render_severity_and_effort(console, findings, gaps, lang)
    _render_gap_list(console, gaps, lang)
    _render_gap_details(console, gaps, lang)
    _render_top_objects(findings, console, lang)
    _render_footer_hints(console, lang, findings)


def _title_text(detector: str, lang: str, style: str = "bold") -> Text:
    """The detector's title, with its `code` spans set apart."""
    text = Text(style=style)
    for i, part in enumerate(messages.title(detector, lang).split("`")):
        text.append(part, style=_CODE_STYLE if i % 2 else None)
    return text


def _render_heading(
    console: Console,
    findings: list[Finding],
    gaps: list[GapGroup],
    objects_scanned: int | None,
    elapsed_seconds: float | None,
    lang: str,
) -> None:
    console.print()
    heading = Text()
    heading.append("* ", style=f"bold {_ACCENT}")
    heading.append(i18n.t(lang, "report_heading", source=source_name(findings)), style="bold")
    console.print(heading)
    lede = Text("  ", style="dim")
    lede.append(
        i18n.t(
            lang,
            "report_found",
            findings=i18n.count(lang, "finding", len(findings)),
            gaps=i18n.count(lang, "gap", len(gaps)),
        )
    )
    if objects_scanned is not None or elapsed_seconds is not None:
        lede.append(" ")
        if objects_scanned is not None:
            lede.append(i18n.t(lang, "term_scanned", objects=i18n.count(lang, "object", objects_scanned)))
        if elapsed_seconds is not None:
            if objects_scanned is None:
                lede.append(i18n.t(lang, "term_scanned", objects="").rstrip(" :") + ":")
            lede.append(i18n.t(lang, "term_elapsed", s=i18n.number(lang, round(elapsed_seconds, 1))))
        lede.append(".")
    console.print(lede)
    console.print()


def _render_rail(console: Console, gaps: list[GapGroup], lang: str) -> None:
    """The four failure stages, in the order a migration reaches them."""
    per_stage = {stage_key(s): 0 for s in STAGES}
    kinds = {stage_key(s): 0 for s in STAGES}
    for g in gaps:
        per_stage[stage_key(g.stage)] += len(g.findings)
        kinds[stage_key(g.stage)] += 1
    peak = max(per_stage.values()) or 1
    narrow = console.width < 96
    grid = Table.grid(expand=True, padding=(0, 2))
    for _ in range(2 if narrow else 4):
        grid.add_column(ratio=1)
    cells = []
    for stage in STAGES[:-1]:
        key = stage_key(stage)
        n = per_stage[key]
        color = _STAGE_STYLE[key] if n else "grey50"
        cell = Text()
        cell.append("● ", style=color)
        cell.append(i18n.t(lang, f"stage_{key}_name") + "\n", style="bold" if n else "dim")
        cell.append(f"{n}\n", style=f"bold {color}")
        # The bar right under the number, so the bars line up whatever the
        # descriptions below them wrap to.
        cell.append("━" * max(1 if n else 0, round(18 * n / peak)) + "\n", style=color)
        cell.append(i18n.count(lang, "gap", kinds[key]) + "\n", style="dim")
        cell.append(i18n.t(lang, f"stage_{key}_desc"), style="dim")
        cells.append(cell)
    per_row = 2 if narrow else 4
    for i in range(0, len(cells), per_row):
        if i:
            # Two rows of stages: a blank line between, or the second row's
            # names run straight on from the first row's descriptions.
            grid.add_row(*([""] * per_row))
        grid.add_row(*cells[i : i + per_row])
    console.print(grid)
    if per_stage["none"]:
        console.print()
        console.print(
            Text(
                f"{i18n.t(lang, 'stage_none_name')}: {i18n.count(lang, 'finding', per_stage['none'])} - "
                f"{i18n.t(lang, 'stage_none_desc')}.",
                style="dim",
            )
        )
    console.print()


def _render_severity_and_effort(console: Console, findings: list[Finding], gaps: list[GapGroup], lang: str) -> None:
    """Severity split and effort range, labels in one column and values in
    another so that anything that wraps stays under its value."""
    counts = summarize_by_severity(findings)
    total = len(findings)
    legend = Text()
    for name, n in ordered_counts(counts):
        legend.append(f"  {_severity_dot(name)} ", style=_SEVERITY_STYLE.get(name))
        legend.append(f"{name} ")
        legend.append(str(n), style="bold")
    # The bar takes what the line has left after the labels' column and the
    # legend, up to 40, so the legend never wraps away from it.
    labels = max(Text(i18n.t(lang, key)).cell_len for key in ("report_filter_severity", "effort_panel_title"))
    width = max(10, min(40, console.width - labels - 2 - legend.cell_len - len(counts)))
    bar = Text()
    for name, n in ordered_counts(counts):
        bar.append("█" * max(1, round(width * n / total)), style=_SEVERITY_STYLE.get(name, "dim"))
    bar.append_text(legend)

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", no_wrap=True)
    grid.add_column(ratio=1)
    grid.add_row(i18n.t(lang, "report_filter_severity"), bar)
    lo, hi = estimate_hours(findings)
    grid.add_row(
        i18n.t(lang, "effort_panel_title"), Text(i18n.t(lang, "report_effort_range", lo=i18n.hours(lang, lo), hi=i18n.hours(lang, hi)), style="bold")
    )
    grid.add_row("", Text(i18n.t(lang, "report_effort_caveat"), style="dim"))
    if distinct_detector_count(findings) < total:
        note = i18n.t(
            lang,
            "term_effort_patterns",
            gaps=i18n.count(lang, "gap", len(gaps)),
            findings=i18n.count(lang, "finding", total),
        )
        grid.add_row("", Text(note, style="dim"))
    console.print(grid)
    console.print()


def _render_gap_list(console: Console, gaps: list[GapGroup], lang: str) -> None:
    console.print(Text(i18n.t(lang, "report_gaps_heading"), style="bold"))
    table = Table(box=None, show_header=False, expand=True, pad_edge=False, padding=(0, 1))
    table.add_column(width=1, no_wrap=True)
    table.add_column(width=7, no_wrap=True)
    table.add_column(ratio=1, overflow="fold")
    table.add_column(justify="right", no_wrap=True)
    table.add_column(justify="right", no_wrap=True)
    table.add_column(no_wrap=True)
    for g in gaps:
        gap = gap_by_detector(g.detector)
        table.add_row(
            Text("▌", style=_STAGE_STYLE[stage_key(g.stage)]),
            Text(f"GAP-{gap.number}" if gap is not None else "—", style="dim"),
            _title_text(g.detector, lang, style=""),
            Text(i18n.count(lang, "finding", len(g.findings))),
            Text(i18n.count(lang, "object", g.objects), style="dim"),
            Text(g.severity, style=_SEVERITY_STYLE.get(g.severity, "")),
        )
    console.print(table)
    console.print()


def _render_gap_details(console: Console, gaps: list[GapGroup], lang: str) -> None:
    console.print(Text(i18n.t(lang, "term_details_heading"), style="bold"))
    for g in gaps:
        gap_number, failure_stage = gap_metadata(g.detector)
        body: list[RenderableType] = []
        if gap_number is not None:
            if failure_stage is not None:
                line = i18n.t(
                    lang,
                    "explanation_gap_stage_line",
                    gap=f"GAP-{gap_number}",
                    stage=i18n.t(lang, f"failure_stage_short_{failure_stage}"),
                )
                body.append(Text(f"{line} - {i18n.t(lang, f'stage_{failure_stage}_desc')}", style=_STAGE_STYLE[failure_stage]))
            else:
                body.append(Text(f"GAP-{gap_number}", style="dim"))
        # What to do before why: the same order as the TUI and the HTML.
        hint = messages.remediation_hint(g.detector, lang)
        if hint:
            fix = Text()
            fix.append(f"{i18n.t(lang, 'report_gap_fix')}: ", style=f"bold {_ACCENT}")
            fix.append(hint)
            body.append(fix)
        command = prepare_command(g.detector)
        if command is not None:
            before = Text()
            before.append(f"{i18n.t(lang, 'report_gap_prepare')}: ", style=f"bold {_ACCENT}")
            before.append(command, style=_CODE_STYLE)
            body.append(before)
        recipe = recipe_for(g.detector)
        if recipe is not None:
            body.append(_recipe_text(recipe, lang))
        for message_id in dict.fromkeys(f.message_id for f in g.findings):
            body.append(Text(messages.text(message_id, lang)))
        where = Table.grid(padding=(0, 2))
        where.add_column(style="dim", no_wrap=True, overflow="ellipsis", max_width=48)
        where.add_column(style="bold", no_wrap=True, overflow="ellipsis", max_width=40)
        where.add_column(style=_ACCENT, overflow="fold")
        ordered = sorted(g.findings, key=lambda f: (f.source_file, f.line))
        for f in ordered[:_OCCURRENCES_SHOWN]:
            place = f"{f.source_file or '—'}:{f.line}" if f.line else (f.source_file or "—")
            where.add_row(Text(place), Text(f.object_name), Text(f.snippet))
        places: list[RenderableType] = [Text(f"{i18n.t(lang, 'report_gap_where')}:", style="bold"), where]
        rest = len(ordered) - _OCCURRENCES_SHOWN
        if rest > 0:
            places.append(
                Text(i18n.t(lang, "term_more_findings", findings=i18n.count(lang, "finding", rest)), style="dim")
            )
        body.append(Group(*places))
        title = Text.assemble(" ", (g.detector, "bold"), "  ", (g.severity, _SEVERITY_STYLE.get(g.severity, "")), " ")
        console.print(
            Panel(
                Group(*_spaced(body)),
                title=title,
                title_align="left",
                border_style=_STAGE_STYLE[stage_key(g.stage)],
                padding=(0, 1),
            )
        )


def _recipe_text(recipe: Recipe, lang: str) -> Text:
    """'Recipe: <title>' and the page's address on the next line -- spelled
    out rather than only a terminal hyperlink, which many terminals and
    every log file would drop."""
    url = recipe_url(recipe, lang)
    text = Text()
    text.append(f"{i18n.t(lang, 'report_gap_recipe')}: ", style=f"bold {_ACCENT}")
    text.append(recipe.title(lang), style=f"link {url}")
    text.append("\n")
    text.append(url, style="dim")
    return text


def _spaced(parts: list[RenderableType]) -> list[RenderableType]:
    """The parts of a gap's panel with an empty line between each."""
    out: list[RenderableType] = []
    for i, part in enumerate(parts):
        if i:
            out.append(Text())
        out.append(part)
    return out


def _render_top_objects(findings: list[Finding], console: Console, lang: str = "ru") -> None:
    per_object = Counter(f.object_name for f in findings)
    if len(per_object) < 2:
        return
    console.print()
    console.print(Text(i18n.t(lang, "report_top_objects"), style="bold"))
    grid = Table.grid(padding=(0, 3))
    grid.add_column(no_wrap=True, overflow="ellipsis", max_width=60)
    grid.add_column(justify="right", style="dim")
    for name, n in per_object.most_common(_TOP_OBJECTS_LIMIT):
        grid.add_row(Text(name), Text(i18n.count(lang, "finding", n)))
    console.print(grid)
    rest = len(per_object) - _TOP_OBJECTS_LIMIT
    if rest > 0:
        console.print(Text(i18n.t(lang, "term_more_objects", objects=i18n.count(lang, "object", rest)), style="dim"))


def render_baseline_diff(diff: BaselineDiff, console: Console | None = None, lang: str = "ru") -> None:
    """Prints a NEW/RESOLVED/UNCHANGED summary against a --baseline
    snapshot — see baseline.py for how findings are matched across scans.
    Deliberately its own panel, printed in addition to (not instead of)
    the normal report: --baseline augments a scan, it doesn't replace
    what the scan itself found."""
    console = console or Console()

    counts = Table.grid(padding=(0, 2))
    counts.add_column(style="dim")
    counts.add_column()
    counts.add_row("NEW", Text(str(len(diff.new)), style="bold #E5484D" if diff.new else "bold"))
    counts.add_row("RESOLVED", Text(str(len(diff.resolved)), style="bold #46A758"))
    counts.add_row("UNCHANGED", Text(str(diff.unchanged_count), style="dim"))

    parts: list[Text | Table] = [counts]

    if diff.new:
        # Text.append() takes its string as literal content, same as every
        # other place in this module that interpolates finding-derived text
        # (object_name, detector, snippet) -- it does not parse Rich markup,
        # unlike a raw f-string handed to console.print() directly. See the
        # module-level comment above the "Все находки" table for why that
        # distinction matters here (arbitrary text straight from the Oracle
        # source being scanned).
        new_list = Text("\n")
        new_list.append(i18n.t(lang, "new_findings_label"), style="bold #E5484D")
        for f in diff.new:
            new_list.append(f"  • {f.object_name}", style="bold")
            new_list.append(f"  [{f.detector}]  {f.snippet}\n", style="dim")
        parts.append(new_list)

    console.print(
        Panel(
            Group(*parts),
            title=i18n.t(lang, "baseline_panel_title"),
            title_align="left",
            border_style=_ACCENT,
        )
    )


# What comes after a scan, in the order a migration gets there: keep a
# list of the work, convert, repair what is mechanical, then ask a real
# PostgreSQL. Shown after every report, so the next command is never
# something to look up.
_NEXT_STEPS = (
    ("next_step_checklist", "ora2pg-gap-report ... -f checklist -o MIGRATION.md"),
    ("next_step_fix", "ora2pg-gap-report --fix --write out/"),
    ("next_step_load_check", "ora2pg-gap-report --load-check docker out/"),
)


def _render_footer_hints(console: Console, lang: str = "ru", findings: list[Finding] | None = None) -> None:
    console.print()
    console.print(Text(i18n.t(lang, "next_steps_heading"), style="bold"))
    steps = Table.grid(padding=(0, 2))
    steps.add_column(style=f"bold {_ACCENT}", no_wrap=True)
    steps.add_column(style="dim")
    steps.add_column(style=_CODE_STYLE, overflow="fold")
    # A MySQL or T-SQL scan needs its dialect on the commands that follow,
    # or --fix runs Oracle's fixes and --load-check explains with Oracle's
    # detectors.
    dialect = source_dialect(findings or [])
    flag = "" if dialect == "oracle" else f" --dialect {dialect}"
    plan = [(key, command.replace("ora2pg-gap-report", f"ora2pg-gap-report{flag}", 1)) for key, command in _NEXT_STEPS]
    # Only when this scan found something --prepare removes: then it is the
    # first thing to do, before ora2pg ever reads the dump.
    prepare = next(
        (c for c in (prepare_command(d) for d in dict.fromkeys(f.detector for f in findings or ())) if c), None
    )
    if prepare is not None:
        plan.insert(0, ("next_step_prepare", prepare))
    for n, (key, command) in enumerate(plan, 1):
        steps.add_row(str(n), i18n.t(lang, key), command)
    console.print(steps)
    console.print()
    console.print(
        f"[dim]{i18n.t(lang, 'footer_hint_severity_label')}[/dim] "
        "ora2pg-gap-report ... --severity high"
    )
    console.print(
        f"[dim]{i18n.t(lang, 'footer_hint_object_label')}[/dim] ora2pg-gap-report ... --object PKG_NAME"
    )


_VERIFICATION_STATUS_STYLE = {
    "still_present": "bold #E5484D",
    "not_detected": "bold #46A758",
    "not_verifiable": "dim",
}


def _render_new_in_output(
    entries: list[NewInOutput], console: Console, lang: str
) -> None:
    """The other half of --verify's question. The results table below can
    only speak about detectors the baseline already knew about; this
    section is for constructs that appear in ora2pg's output and were
    never in the Oracle source -- introduced by the conversion itself.
    Silent when there are none, so a clean run reads exactly as it did
    before this section existed."""
    if not entries:
        return

    table = Table(show_lines=True, expand=True)
    table.add_column(i18n.t(lang, "verify_col_detector"), style="bold", no_wrap=True, overflow="ellipsis")
    table.add_column(i18n.t(lang, "verify_col_gap"), width=9)
    table.add_column(i18n.t(lang, "verify_new_col_count"), justify="right", width=12)
    for e in entries:
        table.add_row(
            Text(e.detector),
            Text(f"GAP-{e.gap_number}" if e.gap_number else "—"),
            Text(str(e.count), style="#D9A21B"),
        )

    console.print()
    console.print(
        Panel(
            table,
            title=i18n.t(lang, "verify_new_panel_title"),
            title_align="left",
            border_style="#D9A21B",
        )
    )
    console.print(f"[dim]{i18n.t(lang, 'verify_new_footer_note')}[/dim]")


def render_verification(
    results: list[DetectorVerification],
    console: Console | None = None,
    lang: str = "ru",
    new_in_output: list[NewInOutput] | None = None,
) -> None:
    """Renders the --verify report: one row per detector present in the
    pre-migration baseline, comparing it against a scan of ora2pg's
    generated PostgreSQL output. See verification.py's module docstring
    for what STILL_PRESENT/NOT_DETECTED/NOT_VERIFIABLE actually mean --
    deliberately not PASS/FAIL and deliberately not a percentage, for the
    same reason effort_estimator.py never produces a single confident
    number: NOT_DETECTED is "the pattern wasn't found", not "proven
    fixed", and that distinction matters enough to spell out in the
    report itself (see the footer note), not just in a docstring."""
    console = console or Console()
    console.print()
    console.print(Text(i18n.t(lang, "term_verify_heading"), style="bold"))
    console.print()

    counts = {"still_present": 0, "not_detected": 0, "not_verifiable": 0}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="dim")
    summary.add_column()
    summary.add_row(
        i18n.t(lang, "verify_summary_baseline_detectors"),
        Text(str(len(results)), style="bold"),
    )
    summary.add_row(
        i18n.t(lang, "verify_summary_still_present"),
        Text(str(counts["still_present"]), style=_VERIFICATION_STATUS_STYLE["still_present"]),
    )
    summary.add_row(
        i18n.t(lang, "verify_summary_not_detected"),
        Text(str(counts["not_detected"]), style=_VERIFICATION_STATUS_STYLE["not_detected"]),
    )
    summary.add_row(
        i18n.t(lang, "verify_summary_not_verifiable"),
        Text(str(counts["not_verifiable"]), style=_VERIFICATION_STATUS_STYLE["not_verifiable"]),
    )
    if new_in_output:
        # Only when there is something to report: an always-present "0"
        # row would imply the other four counts and this one are the same
        # kind of number, and they aren't -- those four partition the
        # baseline, this one counts detectors the baseline never had.
        summary.add_row(
            i18n.t(lang, "verify_summary_new_in_output"),
            Text(str(len(new_in_output)), style="#D9A21B"),
        )
    console.print(Panel(summary, title=i18n.t(lang, "verify_panel_title"), title_align="left", border_style=_ACCENT))

    _render_new_in_output(new_in_output or [], console, lang)

    if not results:
        return

    table = Table(show_lines=True, expand=True)
    table.add_column(i18n.t(lang, "verify_col_detector"), style="bold", no_wrap=True, overflow="ellipsis")
    table.add_column(i18n.t(lang, "verify_col_gap"), width=9)
    table.add_column(i18n.t(lang, "verify_col_before"), justify="right", width=12)
    table.add_column(i18n.t(lang, "verify_col_after"), justify="right", width=12)
    table.add_column(i18n.t(lang, "verify_col_status"), width=16)

    for r in results:
        status_style = _VERIFICATION_STATUS_STYLE.get(r.status, "")
        table.add_row(
            Text(r.detector),
            Text(f"GAP-{r.gap_number}" if r.gap_number else "—"),
            Text(str(r.baseline_count)),
            Text(str(r.post_migration_count) if r.status != "not_verifiable" else "—"),
            Text(r.status.upper(), style=status_style),
        )
    console.print(table)
    console.print()
    console.print(f"[dim]{i18n.t(lang, 'verify_footer_note')}[/dim]")


# --load-check ---------------------------------------------------------------

_LOAD_CATEGORY_STYLE = {
    "fixable": "bold #46A758",
    "gap": "bold #E5484D",
    "unknown": "bold #D9A21B",
    "dependency": "grey62",
    "environment": "dim",
}
# How many errors of one category the terminal lists before pointing at
# --format json, which carries all of them.
_LOAD_ERRORS_SHOWN = 10
_INCLUDE_COMMANDS = ("\\i ", "\\ir ", "\\include ", "\\include_relative ")


def _short_path(path: str) -> str:
    """The path as given, unless it is long: then its last two parts."""
    if len(path) <= 60:
        return path
    parts = path.replace("\\", "/").split("/")
    return ".../" + "/".join(parts[-2:])


def _print_error_line(console: Console, where: str, error: LoadError) -> None:
    """One failed statement on screen: file:line, SQLSTATE and the message,
    as a grid so a message that wraps continues under itself, not under the
    file name."""
    line = Table.grid(padding=(0, 2))
    line.add_column(no_wrap=True)
    line.add_column(no_wrap=True)
    line.add_column(overflow="fold")
    line.add_row(
        Text(f"{where}:{error.line}", style=_CODE_STYLE),
        Text(error.sqlstate, style="dim"),
        Text(error.message),
    )
    console.print(Padding(line, (0, 0, 0, 2)))


def _print_missing_objects(console: Console, errors: list[LoadError], where: Callable[[str], str], lang: str) -> None:
    """The missing-object errors by the object they miss: a first run on a
    large schema has many, and they come down to a few objects -- each
    either made by a statement that failed above (fix that one) or not in
    the loaded files at all."""
    # By the bare name: logger.tab_param and tab_param are one type, named
    # with and without its schema.
    groups: dict[str, list[LoadError]] = {}
    for error in errors:
        if error.missing:
            groups.setdefault(error.missing.lower().rsplit(".", 1)[-1], []).append(error)
    if not groups:
        return
    console.print(Text("  " + i18n.t(lang, "load_check_missing_objects", n=len(groups)), style="dim"))
    table = Table.grid(padding=(0, 2))
    table.add_column(style=_CODE_STYLE, no_wrap=True)
    table.add_column(justify="right", no_wrap=True)
    table.add_column()
    ordered = sorted(groups.values(), key=lambda g: (-len(g), g[0].missing or ""))
    for group in ordered:
        shown_name = max((e.missing or "" for e in group), key=len)  # the qualified spelling, if any
        cause = next((e.caused_by for e in group if e.caused_by is not None), None)
        if cause is not None:
            file, line = cause
            why = Text(i18n.t(lang, "load_check_missing_failed", where=f"{Path(where(file)).name}:{line}"))
        else:
            why = Text(i18n.t(lang, "load_check_missing_absent"), style="dim")
        table.add_row(shown_name, i18n.count(lang, "statement", len(group)), why)
    console.print(Padding(table, (0, 0, 0, 4)))


def render_load_check(
    result: LoadCheckResult,
    console: Console | None = None,
    lang: str = "ru",
    full: bool = False,
    relative_to: Path | None = None,
) -> None:
    """The --load-check report: what failed, grouped by what to do about
    it -- what --fix repairs first, then known gaps, then errors the
    registry does not know, then the echoes of earlier failures and the
    statements the check itself could not run. Each error once, with the
    file and line PostgreSQL pointed at. On screen each group shows its
    first ten; `full` (a report written to a file) shows every error with
    its whole path, or the path from `relative_to` (--migrate's OUT_DIR,
    where the file is written)."""
    shown = None if full else _LOAD_ERRORS_SHOWN

    def where(path: str) -> str:
        if relative_to is not None:
            try:
                return Path(path).resolve().relative_to(relative_to.resolve()).as_posix()
            except ValueError:
                return path
        return path if full else _short_path(path)

    console = console or Console()
    console.print()
    heading = Text()
    heading.append("* ", style=f"bold {_ACCENT}")
    heading.append(i18n.t(lang, "load_check_heading"), style="bold")
    console.print(heading)
    console.print()

    files = i18n.count(lang, "file", len(result.files))
    # after "из" (from): "из 1 файла", "из 3 файлов"
    files_of = i18n.count(lang, "file_of", len(result.files))
    statements = i18n.count(lang, "statement", result.statements)
    by_category: dict[str, list[LoadError]] = {c: [] for c in CATEGORIES}
    for error in result.errors:
        by_category[error.category].append(error)

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="dim")
    summary.add_column()
    server = result.target + (f" ({result.server_version})" if result.server_version else "")
    summary.add_row(i18n.t(lang, "load_check_server"), Text(server))
    summary.add_row(
        i18n.t(lang, "load_check_loaded"),
        Text(i18n.t(lang, "load_check_loaded_value", files=files, statements=statements)),
    )
    failing = sum(len(by_category[c]) for c in CATEGORIES if c in FAILING_CATEGORIES)
    summary.add_row(
        i18n.t(lang, "load_check_failed_label"),
        Text(str(failing), style="bold #E5484D" if failing else "bold #46A758"),
    )
    for category in CATEGORIES:
        if by_category[category]:
            summary.add_row(
                Text("  " + i18n.t(lang, f"load_check_cat_{category}")),
                Text(str(len(by_category[category])), style=_LOAD_CATEGORY_STYLE[category]),
            )
    console.print(
        Panel(
            summary,
            title=i18n.t(lang, "load_check_panel_title"),
            title_align="left",
            border_style=_ACCENT,
            expand=False,
        )
    )

    if not result.files:
        console.print(Text(i18n.t(lang, "load_check_nothing_loaded"), style="bold #D9A21B"))
    elif not result.errors and result.incomplete:
        # Not "everything loaded": the skipped files below were never tried.
        console.print(
            Text(
                i18n.t(
                    lang,
                    "load_check_clean_but_skipped",
                    statements=statements,
                    files=files_of,
                    skipped=i18n.count(lang, "file", len(result.skipped_files)),
                ),
                style="bold #D9A21B",
            )
        )
    elif not result.errors:
        console.print(Text(i18n.t(lang, "load_check_clean", statements=statements, files=files_of), style="bold #46A758"))

    for category in CATEGORIES:
        errors = by_category[category]
        if not errors:
            continue
        console.print()
        title = Text()
        title.append("● ", style=_LOAD_CATEGORY_STYLE[category])
        title.append(i18n.t(lang, f"load_check_section_{category}"), style="bold")
        title.append(f"  {len(errors)}", style="dim")
        console.print(title)
        if category == "dependency":
            _print_missing_objects(console, errors, where, lang)
        for error in errors[:shown]:
            if full:
                # A file keeps each error on one line, however long.
                flat = Text("  ")
                flat.append(f"{where(error.file)}:{error.line}", style=_CODE_STYLE)
                flat.append(f"  {error.sqlstate}  ", style="dim")
                flat.append(error.message)
                console.print(flat)
            else:
                _print_error_line(console, where(error.file), error)

            if error.context and category in ("gap", "unknown", "fixable"):
                console.print(Padding(Text(error.context, style="dim"), (0, 0, 0, 4), expand=False))
            if error.detector is not None:
                about = Text()
                if error.gap_number is not None:
                    about.append(f"GAP-{error.gap_number} · ", style="bold")
                    about.append_text(_title_text(error.detector, lang, style=""))
                else:
                    about.append(i18n.t(lang, "load_check_hint_detector", detector=error.detector))
                console.print(Padding(about, (0, 0, 0, 4), expand=False))
            if category == "fixable":
                hint = Text("-> " + i18n.t(lang, "load_check_hint_fixable", file=error.file), style=_ACCENT)
                console.print(Padding(hint, (0, 0, 0, 4), expand=False))
            elif category == "gap" and error.gap_number is not None:
                hint = Text("-> " + i18n.t(lang, "load_check_hint_gap", number=error.gap_number), style=_ACCENT)
                console.print(Padding(hint, (0, 0, 0, 4), expand=False))
            recipe = recipe_for(error.detector) if error.detector is not None and category == "gap" else None
            if recipe is not None:
                console.print(Padding(_recipe_text(recipe, lang), (0, 0, 0, 4), expand=False))
            if error.echoes:
                echoes = Text(
                    "+ " + i18n.t(lang, "load_check_echoes", n=i18n.count(lang, "statement", error.echoes)),
                    style=_ACCENT,
                )
                console.print(Padding(echoes, (0, 0, 0, 4), expand=False))
        if shown is not None and len(errors) > shown:
            console.print(
                Text(
                    "  "
                    + i18n.t(
                        lang, "load_check_more", errors=i18n.count(lang, "error", len(errors) - _LOAD_ERRORS_SHOWN)
                    ),
                    style="dim",
                )
            )
        if category in ("unknown", "dependency", "environment"):
            note = Text(i18n.t(lang, f"load_check_note_{category}"), style="dim")
            console.print(Padding(note, (0, 0, 0, 2), expand=False))

    console.print()
    for file, item in result.neutralised:
        if item.kind == "meta" and item.text.lower().startswith(_INCLUDE_COMMANDS):
            console.print(
                i18n.t(lang, "load_check_include_skipped", file=escape(file), line=item.line, command=escape(item.text))
            )
    kinds = Counter(item.kind for _, item in result.neutralised)
    if kinds:
        items = ", ".join(
            i18n.t(lang, f"load_check_neutralised_{kind}", n=kinds[kind])
            for kind in ("meta", "transaction", "setting")
            if kinds[kind]
        )
        console.print(Text(i18n.t(lang, "load_check_neutralised", items=items), style="dim"))
    for skipped in result.skipped_files:
        if skipped.reason == "unterminated":
            console.print(i18n.t(lang, "load_check_skipped_unterminated", file=escape(skipped.file), line=skipped.line))
        else:
            console.print(
                i18n.t(lang, "load_check_skipped_unreadable", file=escape(skipped.file), detail=escape(skipped.detail or ""))
            )
    console.print(Text(i18n.t(lang, "load_check_footer"), style="dim"))


# --migrate ------------------------------------------------------------------


def render_migration(
    result: "MigrationResult",
    load: LoadCheckResult | None,
    console: Console | None = None,
    lang: str = "ru",
    load_check_asked: bool = False,
    in_tui: bool = False,
) -> None:
    """The --migrate summary: one line per step, what it did and where its
    files are, then the load result and what to open first. `in_tui`
    words the next steps for the TUI's migrate screen, which has a
    checkbox and a Run button instead of flags and a command."""
    console = console or Console()
    console.print()
    heading = Text()
    heading.append("* ", style=f"bold {_ACCENT}")
    heading.append(i18n.t(lang, "migrate_heading", source=source_name(result.findings)), style="bold")
    console.print(heading)
    console.print(Text(f"  {result.out_dir}", style="dim"))
    console.print()

    gaps = len({f.detector for f in result.findings})
    steps = Table.grid(padding=(0, 2))
    steps.add_column(style=f"bold {_ACCENT}", no_wrap=True)
    steps.add_column(style="bold", no_wrap=True)
    steps.add_column()
    steps.add_column(style=_CODE_STYLE)
    steps.add_row(
        "1",
        i18n.t(lang, "migrate_row_scan"),
        i18n.t(
            lang,
            "migrate_row_scan_value",
            findings=i18n.count(lang, "finding", len(result.findings)),
            gaps=i18n.count(lang, "gap", gaps),
        ),
        "report.html, MIGRATION.md",
    )
    steps.add_row(
        "2",
        i18n.t(lang, "migrate_row_prepare"),
        i18n.t(lang, "migrate_row_prepare_value", n=result.prepared_rewrites),
        "prepared/",
    )
    kinds = ", ".join(p.stem.split("_", 1)[1].rsplit("_output", 1)[0] for p in result.converted) or "-"
    steps.add_row(
        "3",
        i18n.t(lang, "migrate_row_convert"),
        i18n.t(lang, "migrate_row_convert_value", files=i18n.count(lang, "file", len(result.converted)), kinds=kinds),
        "converted/",
    )
    steps.add_row(
        "4",
        i18n.t(lang, "migrate_row_fix"),
        i18n.t(lang, "migrate_row_fix_value", n=result.fixes, m=result.source_fixes),
        "converted/",
    )
    if load is None:
        load_text = Text(
            i18n.t(
                lang,
                "migrate_row_load_nothing"
                if load_check_asked
                else "migrate_row_load_skipped_tui" if in_tui else "migrate_row_load_skipped",
            ),
            style="dim",
        )
        load_where = ""
    elif load.incomplete and not load.failed:
        load_text = Text(
            i18n.t(lang, "migrate_row_load_incomplete", files=i18n.count(lang, "file", len(load.skipped_files))),
            style="bold #D9A21B",
        )
        load_where = "load-check.txt"
    elif not load.failed:
        load_text = Text(
            i18n.t(lang, "migrate_row_load_clean", statements=i18n.count(lang, "statement", load.statements)),
            style="bold #46A758",
        )
        load_where = "load-check.txt"
    else:
        failing = [e for e in load.errors if e.category in FAILING_CATEGORIES]
        load_text = Text(
            i18n.t(
                lang,
                "migrate_row_load_failed",
                errors=i18n.count(lang, "error", len(failing)),
                statements=i18n.count(lang, "statement_of", load.statements),
            ),
            style="bold #E5484D",
        )
        load_where = "load-check.txt"
    steps.add_row("5", i18n.t(lang, "migrate_row_load"), load_text, load_where)
    console.print(steps)

    console.print()
    console.print(Text(i18n.t(lang, "next_steps_heading"), style="bold"))
    nxt = Table.grid(padding=(0, 2))
    nxt.add_column(style=f"bold {_ACCENT}", no_wrap=True)
    nxt.add_column()
    nxt.add_row("-", i18n.t(lang, "migrate_next_report"))
    nxt.add_row("-", i18n.t(lang, "migrate_next_checklist"))
    if load is not None and (load.failed or load.incomplete):
        nxt.add_row("-", i18n.t(lang, "migrate_next_load"))
    elif load is None and not load_check_asked:
        nxt.add_row("-", i18n.t(lang, "migrate_next_add_load_check_tui" if in_tui else "migrate_next_add_load_check"))
    nxt.add_row("-", i18n.t(lang, "migrate_next_rerun_tui" if in_tui else "migrate_next_rerun"))
    console.print(nxt)
