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
level (LOW/MEDIUM/HIGH/...), per-category "compatibility %" numbers, or
an auto-detected Oracle version. Those would need a scoring methodology
this project doesn't have and hasn't calibrated against real migrations
— showing a confident-looking number with no real basis behind it is
exactly the overclaiming this project's own effort estimate deliberately
avoids (see effort_estimator.py's docstring). Only counts and ranges
genuinely computed from the findings appear here. The "Рекомендации"
section below is the one apparent exception — but each line is just the
existing per-detector remediation hint attached to a real count, not a
new synthesized recommendation.
"""

from rich.console import Console, Group
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

# One short imperative line per detector, for the "Рекомендации" section —
# a compact index into the full explanation already shown per-finding
# below, not new advice. Every detector shipped in this project has an
# entry here; _render_recommended_actions() still falls back to a generic
# line for anything unrecognized (e.g. a third-party detector added via
# this module directly, not through cli.py's registered list) rather than
# crashing on it.
_REMEDIATION_HINT = {
    "autonomous_tx": "Проверить dblink-перенос вручную — сетевая зависимость может быть неприемлема в изолированном контуре",
    "compound_triggers": "Разбить на отдельные обычные триггеры (BEFORE/AFTER × STATEMENT/ROW) с общим состоянием через таблицу",
    "dbms_utl_calls": "Переписать вручную или подключить расширение orafce, если для вызова там есть эквивалент",
    "connect_by": "Заменить LEVEL на настоящую колонку-счётчик в сгенерированном WITH RECURSIVE",
    "merge_delete_clause": "Разбить MERGE на две ветки WHEN MATCHED со взаимоисключающими условиями вместо DELETE WHERE",
    "bulk_collect": "Переписать TYPE/BULK COLLECT на массив PostgreSQL (type[]) или временную таблицу, FORALL — на цикл или UNNEST()",
    "database_link": "Настроить postgres_fdw/dblink с реальными connection-параметрами удалённой базы вместо @dblink_name",
    "model_clause": "Переписать вручную на оконные функции или рекурсивные CTE — прямого эквивалента MODEL в PostgreSQL нет",
    "pivot_clause": "Переписать на условную агрегацию (FILTER/CASE WHEN) или расширение tablefunc (crosstab())",
    "object_type": "Переписать на composite type + отдельные функции — у PostgreSQL нет объектных типов с методами",
    "with_function": "Вынести встроенную функцию в обычную функцию/процедуру PostgreSQL вручную — ora2pg ломает структуру запроса",
    "flashback_query": "Спроектировать отдельный механизм истории/аудита — прямого эквивалента AS OF в PostgreSQL нет",
    "global_temp_table": "Добавить 'ON COMMIT DELETE ROWS' вручную в определение временной таблицы — ora2pg теряет секцию ON COMMIT",
    "table_partitioning": "Пересоздать партиции вручную (CREATE TABLE ... PARTITION OF ...) — ora2pg отбрасывает секционирование полностью",
    "connect_by_nocycle": "Полностью переписать вручную на WITH RECURSIVE — конвертация NOCYCLE/ORDER SIBLINGS BY разваливает структуру блока",
    "context_object": "Переписать на current_setting()/set_config() или Row-Level Security (CREATE POLICY) — прямого аналога CREATE CONTEXT нет",
    "insert_all": "Разбить на набор отдельных INSERT INTO ... SELECT ... — по одному на каждую ветку WHEN/INTO",
    "json_table": "Переписать на jsonb_to_recordset()/jsonb_array_elements() с явным приведением типов",
    "external_table": "Настроить foreign table через file_fdw (или fdw под нужный формат) — ora2pg превращает её в обычную таблицу",
    "sql_macro": "Встроить логику макроса как обычное условие/подзапрос прямо в вызывающий код — SQL_MACRO конвертируется в обычную функцию",
    "invisible_column": "Явно перечислять столбцы в SELECT/INSERT там, где скрытие было важно — PostgreSQL не имеет аналога INVISIBLE",
    "collection_type": "Переписать на встроенный массив (datatype[]) или отдельную связанную таблицу — ora2pg полностью теряет объявление коллекционного типа",
}


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
    _render_banner(console)

    if not findings:
        empty_message = Text("Проблемных конструкций не найдено.")
        if objects_scanned is not None:
            empty_message.append(f"\nОбъектов просканировано: {objects_scanned}")
        if elapsed_seconds is not None:
            empty_message.append(f"\nВремя анализа: {elapsed_seconds:.1f} с", style="dim")
        console.print(Panel(empty_message, border_style="green"))
        return

    counts = summarize_by_severity(findings)
    lo, hi = estimate_hours(findings)

    _render_run_info(console, len(findings), objects_scanned, elapsed_seconds)
    _render_findings_summary(console, counts)
    _render_top_objects(findings, console)
    _render_recommended_actions(findings, console)

    # Finding content (object names, file paths, source snippets) comes
    # straight from the Oracle files being scanned — arbitrary text that
    # must never be interpreted as Rich's own markup language (a path like
    # "notes[/archive].sql" would otherwise raise MarkupError, and content
    # that happens to look like a style tag, e.g. "arr[i][j]", would be
    # silently stripped instead of shown verbatim).
    table = Table(show_lines=True, expand=True, title="Все находки")
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

    _render_effort_panel(console, lo, hi)
    _render_footer_hints(console)


def _render_banner(console: Console) -> None:
    banner = Text(justify="center")
    banner.append("ORACLE → POSTGRESQL MIGRATION GAP REPORT\n", style="bold")
    banner.append("ora2pg-gap-report", style="dim")
    console.print(Panel(banner, border_style="blue"))


def _render_run_info(
    console: Console, finding_count: int, objects_scanned: int | None, elapsed_seconds: float | None
) -> None:
    info = Table.grid(padding=(0, 2))
    info.add_column(style="dim")
    info.add_column()
    if objects_scanned is not None:
        info.add_row("Объектов просканировано", Text(str(objects_scanned), style="bold"))
    info.add_row("Найдено проблемных объектов", Text(str(finding_count), style="bold"))
    if elapsed_seconds is not None:
        info.add_row("Время анализа", Text(f"{elapsed_seconds:.1f} с", style="dim"))
    console.print(Panel(info, border_style="cyan"))


def _render_findings_summary(console: Console, counts: dict[str, int]) -> None:
    body = Text()
    for i, (name, n) in enumerate(ordered_counts(counts)):
        if i:
            body.append("\n")
        style = _SEVERITY_STYLE.get(name)
        body.append(f"{_severity_dot(name)} ", style=style)
        body.append(f"{name.upper():<8}", style=style)
        body.append(str(n), style=style)
    console.print(Panel(body, title="Находки по severity", title_align="left", border_style="cyan"))


def _render_effort_panel(console: Console, lo: float, hi: float) -> None:
    mid = (lo + hi) / 2
    rows = Table.grid(padding=(0, 2))
    rows.add_column(style="dim")
    rows.add_column()
    rows.add_row("Лучший случай", Text(f"{lo:g} ч", style="bold"))
    rows.add_row("Среднее", Text(f"{mid:g} ч", style="bold"))
    rows.add_row("Худший случай", Text(f"{hi:g} ч", style="bold"))

    body = Text()
    body.append("— неоткалиброванная эвристика по severity, не измерение", style="dim")

    group = Group(rows, Text(), body)
    console.print(Panel(group, title="Оценка ручной доработки", title_align="left", border_style="blue"))


def _render_footer_hints(console: Console) -> None:
    console.print()
    console.print("[dim]Показать только высокую критичность:[/dim] ora2pg-gap-report ... --severity high")
    console.print("[dim]Сфокусироваться на одном объекте:[/dim]     ora2pg-gap-report ... --object PKG_NAME")


def _render_recommended_actions(findings: list[Finding], console: Console) -> None:
    """One line per detector actually present, count first — a compact
    index into the "Пояснения" section below, not new analysis. Ordered by
    how many findings each detector produced, worst first."""
    by_detector: dict[str, int] = {}
    for f in findings:
        by_detector[f.detector] = by_detector.get(f.detector, 0) + 1

    ranked = sorted(by_detector.items(), key=lambda kv: -kv[1])

    body = Text()
    for i, (detector, n) in enumerate(ranked, start=1):
        if i > 1:
            body.append("\n\n")
        body.append(f"[{i}] ", style="bold")
        body.append(f"{detector}  ")
        body.append(f"({n})\n", style="dim")
        hint = _REMEDIATION_HINT.get(detector, "См. пояснение ниже.")
        body.append(f"    → {hint}", style="dim")

    console.print(Panel(body, title="Рекомендации", title_align="left", border_style="magenta"))


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
