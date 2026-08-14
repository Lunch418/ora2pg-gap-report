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
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .effort_estimator import estimate_hours, ordered_counts, summarize_by_severity
from .models import Finding

_SEVERITY_STYLE = {
    "high": "bold red",
    "medium": "bold yellow",
    "low": "bold green",
}


def render(findings: list[Finding], console: Console | None = None) -> None:
    console = console or Console()

    if not findings:
        console.print(
            Panel(
                "Проблемных конструкций не найдено.",
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
            counts_markup.append(", ")
        counts_markup.append(f"{name}: {n}", style=_SEVERITY_STYLE.get(name))

    summary = Text()
    summary.append("Найдено проблемных объектов: ")
    summary.append(str(len(findings)), style="bold")
    summary.append("  (")
    summary.append_text(counts_markup)
    summary.append(")\n")
    summary.append("Грубая оценка ручной доработки: ")
    summary.append(f"{lo:g}–{hi:g} ч.", style="bold")
    summary.append(
        " — неоткалиброванная эвристика по severity, не измерение", style="dim"
    )
    console.print(Panel(summary, title="ora2pg-gap-report", border_style="cyan"))

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
