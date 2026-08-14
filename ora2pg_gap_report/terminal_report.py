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

from .effort_estimator import estimate_hours, summarize_by_severity
from .models import Finding

_SEVERITY_STYLE = {
    "high": "bold red",
    "medium": "bold yellow",
    "low": "bold green",
}
_SEVERITY_ORDER = ("high", "medium", "low")


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

    parts = [
        f"[{_SEVERITY_STYLE[sev]}]{sev}: {counts[sev]}[/{_SEVERITY_STYLE[sev]}]"
        for sev in _SEVERITY_ORDER
        if counts.get(sev)
    ]
    # any severity value outside high/medium/low (see effort_estimator.py's
    # "other" bucket) still has to be visible, just without a colour to map it to
    parts += [f"{name}: {n}" for name, n in counts.items() if name not in _SEVERITY_ORDER and n]

    summary = (
        f"Найдено проблемных объектов: [bold]{len(findings)}[/bold]  ({', '.join(parts)})\n"
        f"Грубая оценка ручной доработки: [bold]{lo:g}–{hi:g} ч.[/bold] "
        "[dim]— неоткалиброванная эвристика по severity, не измерение[/dim]"
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
        severity_style = _SEVERITY_STYLE.get(f.severity, "bold white")
        table.add_row(
            f.source_file or "—",
            f.object_name,
            str(f.line),
            f"[{severity_style}]{f.severity}[/{severity_style}]",
            f.detector,
            f.snippet,
        )

    console.print(table)

    explanations: dict[tuple[str, str], list[str]] = {}
    for f in findings:
        explanations.setdefault((f.detector, f.message), []).append(f.object_name)

    console.print()
    console.print("[bold]Пояснения[/bold]")
    for (detector, message), objects in explanations.items():
        title = f"{detector} — {len(objects)} объект(ов)"
        console.print(Panel(message, title=title, title_align="left", border_style="dim"))
