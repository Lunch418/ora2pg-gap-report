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

from rich.console import Console, Group, RenderableType
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
from .html_report import STAGES, GapGroup, group_by_gap, source_name, stage_key
from .models import Finding
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
            empty_message.append(i18n.t(lang, "elapsed_inline", s=elapsed_seconds), style="dim")
        console.print(Panel(empty_message, border_style="#46A758"))
        return

    gaps = group_by_gap(findings)
    _render_heading(console, findings, gaps, objects_scanned, elapsed_seconds, lang)
    _render_rail(console, gaps, lang)
    _render_severity_and_effort(console, findings, gaps, lang)
    _render_gap_list(console, gaps, lang)
    _render_gap_details(console, gaps, lang)
    _render_top_objects(findings, console, lang)
    _render_footer_hints(console, lang)


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
            lede.append(i18n.t(lang, "term_elapsed", s=elapsed_seconds))
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
    for i in range(0, len(cells), 2 if narrow else 4):
        grid.add_row(*cells[i : i + (2 if narrow else 4)])
    console.print(grid)
    if per_stage["none"]:
        console.print()
        console.print(
            Text(
                f"{i18n.t(lang, 'stage_none_name')}: {i18n.count(lang, 'finding', per_stage['none'])} — "
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
    bar = Text()
    for name, n in ordered_counts(counts):
        bar.append("█" * max(1, round(40 * n / total)), style=_SEVERITY_STYLE.get(name, "dim"))
    for name, n in ordered_counts(counts):
        bar.append(f"  {_severity_dot(name)} ", style=_SEVERITY_STYLE.get(name))
        bar.append(f"{name} ")
        bar.append(str(n), style="bold")

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", no_wrap=True)
    grid.add_column(ratio=1)
    grid.add_row(i18n.t(lang, "report_filter_severity"), bar)
    lo, hi = estimate_hours(findings)
    grid.add_row(
        i18n.t(lang, "effort_panel_title"), Text(i18n.t(lang, "report_effort_range", lo=i18n.number(lang, lo), hi=i18n.number(lang, hi)), style="bold")
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
                body.append(Text(f"{line} — {i18n.t(lang, f'stage_{failure_stage}_desc')}", style=_STAGE_STYLE[failure_stage]))
            else:
                body.append(Text(f"GAP-{gap_number}", style="dim"))
        # What to do before why: the same order as the TUI and the HTML.
        hint = messages.remediation_hint(g.detector, lang)
        if hint:
            fix = Text()
            fix.append(f"{i18n.t(lang, 'report_gap_fix')}: ", style=f"bold {_ACCENT}")
            fix.append(hint)
            body.append(fix)
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


def _render_footer_hints(console: Console, lang: str = "ru") -> None:
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
