"""Rich-based terminal rendering — presentation only.

Deliberately its own module, not folded into report_generator.py: the
detector library (models.py, detectors/, report_generator.py) stays
importable with zero dependencies; only the CLI's interactive terminal
output pulls in `rich`. report_generator.py's plain JSON/Markdown stay
the machine-readable / redirect-to-a-file formats.

The table itself stays deliberately compact (identifiers truncated with
an ellipsis rather than wrapped mid-word) and the full explanation text
lives in a separate "Пояснения" section below, grouped by the (detector,
message) pairs actually present — every detector in this project emits
the same static explanation for all its findings, so repeating a full
paragraph once per row would be pure noise, and at a realistic terminal
width (or the ~80-column fallback used when output isn't a real tty) a
wide prose column makes the table unreadable regardless.

Deliberately NOT here: a single "migration readiness" score, a risk
level (LOW/MEDIUM/HIGH/...), or per-category "compatibility %" numbers.
Those would need a scoring methodology this project doesn't have and
hasn't calibrated against real migrations — showing a confident-looking
number with no real basis behind it is exactly the overclaiming this
project's own effort estimate deliberately avoids (see
effort_estimator.py's docstring). Only counts and ranges genuinely
computed from the findings appear here.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from .effort_estimator import estimate_hours, ordered_counts, summarize_by_severity
from .models import Finding

_SEVERITY_STYLE = {
    "high": "bold red",
    "medium": "bold yellow",
    "low": "bold green",
}
_TOP_OBJECTS_LIMIT = 10


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
) -> None:
    console = console or Console()

    if not findings:
        empty_message = Text("Проблемных конструкций не найдено.")
        if objects_scanned is not None:
            empty_message.append(f"\nОбъектов просканировано: {objects_scanned}")
        if elapsed_seconds is not None:
            empty_message.append(f"\nВремя анализа: {elapsed_seconds:.1f} с", style="dim")
        console.print(
            Panel(
                empty_message,
                title="ora2pg-gap-report",
                border_style="green",
            )
        )
        return

    counts = summarize_by_severity(findings)
    lo, hi = estimate_hours(findings)

    # Finding content (object names, file paths, source snippets) comes
    # straight from the Oracle files being scanned — arbitrary text that
    # must never be interpreted as Rich's own markup language (a path like
    # "notes[/archive].sql" would otherwise raise MarkupError, and content
    # that happens to look like a style tag, e.g. "arr[i][j]", would be
    # silently stripped instead of shown verbatim). Only the summary/
    # severity strings below are our own trusted, hand-built markup.
    counts_markup = Text()
    for i, (name, n) in enumerate(ordered_counts(counts)):
        if i:
            counts_markup.append("  ")
        counts_markup.append(f"{_severity_dot(name)} ", style=_SEVERITY_STYLE.get(name))
        counts_markup.append(f"{name}: {n}", style=_SEVERITY_STYLE.get(name))

    summary = Text()
    if objects_scanned is not None:
        summary.append("Объектов просканировано: ")
        summary.append(str(objects_scanned), style="bold")
        summary.append("\n")
    summary.append("Найдено проблемных объектов: ")
    summary.append(str(len(findings)), style="bold")
    summary.append("\n")
    summary.append_text(counts_markup)
    summary.append("\n")
    mid = (lo + hi) / 2
    summary.append("Грубая оценка ручной доработки — ")
    summary.append(f"лучший случай: {lo:g} ч", style="bold")
    summary.append(", среднее: ")
    summary.append(f"{mid:g} ч", style="bold")
    summary.append(", худший случай: ")
    summary.append(f"{hi:g} ч", style="bold")
    summary.append("\n")
    summary.append(
        "— неоткалиброванная эвристика по severity, не измерение", style="dim"
    )
    if elapsed_seconds is not None:
        summary.append(f"\nВремя анализа: {elapsed_seconds:.1f} с", style="dim")
    console.print(Panel(summary, title="ora2pg-gap-report", border_style="cyan"))

    _render_top_objects(findings, console)

    table = Table(show_lines=True, expand=True)
    table.add_column("Файл", style="dim", no_wrap=True, overflow="ellipsis", ratio=2)
    table.add_column("Объект", style="bold", no_wrap=True, overflow="ellipsis", ratio=2)
    table.add_column("Строка", justify="right", width=7)
    table.add_column("Severity", width=9)
    table.add_column("Детектор", style="magenta", no_wrap=True, overflow="ellipsis", ratio=2)
    table.add_column("Фрагмент", style="cyan", no_wrap=True, overflow="ellipsis", ratio=2)

    for f in findings:
        severity_style = _SEVERITY_STYLE.get(f.severity)
        table.add_row(
            Text(f.source_file or "—"),
            Text(f.object_name),
            Text(str(f.line)),
            Text(f.severity, style=severity_style),
            Text(f.detector),
            Text(f.snippet),
        )

    console.print(table)

    explanation_counts: dict[tuple[str, str], int] = {}
    for f in findings:
        key = (f.detector, f.message)
        explanation_counts[key] = explanation_counts.get(key, 0) + 1

    console.print()
    console.print("[bold]Пояснения[/bold]")
    for (detector, message), n in explanation_counts.items():
        title = f"{detector} — {n} объект(ов)"
        console.print(Panel(Text(message), title=title, title_align="left", border_style="dim"))


def _render_top_objects(findings: list[Finding], console: Console) -> None:
    """Findings grouped by object, worst-affected first — the same
    findings already in the table below, just re-sliced by "which object
    needs the most attention" instead of one row per finding. Every count
    shown here is a plain tally of real findings, nothing derived or
    estimated."""
    by_object: dict[str, list[Finding]] = {}
    for f in findings:
        by_object.setdefault(f.object_name, []).append(f)

    if len(by_object) <= 1:
        return  # nothing to rank when everything is already one object

    ranked = sorted(
        by_object.items(),
        key=lambda item: (
            -len(item[1]),
            {"high": 0, "medium": 1, "low": 2}.get(_worst_severity({g.severity for g in item[1]}), 3),
            item[0],
        ),
    )

    tree = Tree(Text("Объекты с наибольшим числом находок", style="bold"))
    for object_name, group in ranked[:_TOP_OBJECTS_LIMIT]:
        by_detector: dict[str, list[Finding]] = {}
        for f in group:
            by_detector.setdefault(f.detector, []).append(f)

        branch_label = Text()
        branch_label.append(object_name, style="bold")
        branch_label.append(f"  {len(group)} находок")
        branch = tree.add(branch_label)

        for detector, detector_findings in sorted(
            by_detector.items(), key=lambda kv: -len(kv[1])
        ):
            worst = _worst_severity({g.severity for g in detector_findings})
            leaf = Text()
            leaf.append(f"{_severity_dot(worst)} ", style=_SEVERITY_STYLE.get(worst))
            leaf.append(detector)
            leaf.append(f"  ({len(detector_findings)})", style="dim")
            branch.add(leaf)

    remaining = len(ranked) - _TOP_OBJECTS_LIMIT
    if remaining > 0:
        tree.add(Text(f"… и ещё {remaining} объект(ов)", style="dim"))

    console.print(tree)
    console.print()
