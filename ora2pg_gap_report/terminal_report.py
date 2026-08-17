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

from . import i18n
from .baseline import BaselineDiff
from .effort_estimator import (
    distinct_detector_count,
    estimate_hours,
    ordered_counts,
    summarize_by_severity,
)
from .i18n import REMEDIATION_HINT_EN
from .models import Finding
from .verification import DetectorVerification

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
    "cross_apply": "Переписать на JOIN LATERAL (...) ON true / LEFT JOIN LATERAL (...) ON true — синтаксиса APPLY в PostgreSQL нет",
    "oracle_text": "Переписать на tsvector/tsquery + GIN-индекс (to_tsvector/@@) — ora2pg теряет INDEXTYPE и не переносит CONTAINS/CATSEARCH/MATCHES",
    "recursive_with": "Добавить ключевое слово RECURSIVE вручную (и при наличии CYCLE — переставить её после тела CTE и добавить обязательную секцию USING)",
    "invisible_index": "Проверить, действительно ли индекс должен быть скрыт от оптимизатора — PostgreSQL не имеет аналога INVISIBLE для индексов",
    "read_only_table": "Настроить REVOKE INSERT/UPDATE/DELETE от всех ролей или BEFORE-триггер, отклоняющий DML — ora2pg теряет секцию READ ONLY",
    "materialized_view_log": "Спроектировать обновление материализованных представлений через полный REFRESH MATERIALIZED VIEW — у PostgreSQL нет инкрементального FAST REFRESH",
    "identity_column": "Убрать лишнюю внешнюю пару скобок вокруг опций последовательности вручную — баг подстановки ora2pg, не пропуск конвертации",
    "rowid_type": "Вручную выбрать подходящий тип (обычно text) для столбца, который ora2pg сконвертировал из ROWID/UROWID в oid",
    "sequence_cycle": "Добавить CYCLE вручную в CREATE SEQUENCE, если циклическое поведение действительно нужно",
    "default_on_null": "Переписать вручную на BEFORE-триггер или GENERATED ALWAYS AS (COALESCE(...)) STORED — прямого аналога DEFAULT ... ON NULL в PostgreSQL нет",
    "public_synonym": "Вручную квалифицировать целевую таблицу схемой в определении сгенерированного VIEW",
    "virtual_column": "Учитывать, что сгенерированный триггер молча отбрасывает любое явно присвоенное столбцу значение — добавить проверку на уровне приложения, если эта защита важна",
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
    lang: str = "ru",
) -> None:
    console = console or Console()
    _render_banner(console)

    if not findings:
        empty_message = Text(i18n.t(lang, "no_findings"))
        if objects_scanned is not None:
            empty_message.append(i18n.t(lang, "objects_scanned_inline", n=objects_scanned))
        if elapsed_seconds is not None:
            empty_message.append(i18n.t(lang, "elapsed_inline", s=elapsed_seconds), style="dim")
        console.print(Panel(empty_message, border_style="green"))
        return

    counts = summarize_by_severity(findings)
    lo, hi = estimate_hours(findings)

    _render_run_info(console, len(findings), objects_scanned, elapsed_seconds, lang)
    _render_findings_summary(console, counts, lang)
    _render_top_objects(findings, console, lang)
    _render_recommended_actions(findings, console, lang)

    # Finding content (object names, file paths, source snippets) comes
    # straight from the Oracle files being scanned — arbitrary text that
    # must never be interpreted as Rich's own markup language (a path like
    # "notes[/archive].sql" would otherwise raise MarkupError, and content
    # that happens to look like a style tag, e.g. "arr[i][j]", would be
    # silently stripped instead of shown verbatim).
    table = Table(show_lines=True, expand=True, title=i18n.t(lang, "all_findings_title"))
    table.add_column(i18n.t(lang, "col_file"), style="dim", no_wrap=True, overflow="ellipsis", ratio=2)
    table.add_column(i18n.t(lang, "col_object"), style="bold", no_wrap=True, overflow="ellipsis", ratio=2)
    table.add_column(i18n.t(lang, "col_line"), justify="right", width=7)
    table.add_column(i18n.t(lang, "col_severity"), width=9)
    table.add_column(i18n.t(lang, "col_detector"), style="magenta", no_wrap=True, overflow="ellipsis", ratio=2)
    table.add_column(i18n.t(lang, "col_snippet"), style="cyan", no_wrap=True, overflow="ellipsis", ratio=2)

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
    console.print(f"[bold]{i18n.t(lang, 'explanations_title')}[/bold]")
    for (detector, message), n in explanation_counts.items():
        title = i18n.t(lang, "explanation_panel_title", detector=detector, n=n)
        console.print(Panel(Text(message), title=title, title_align="left", border_style="dim"))

    _render_effort_panel(console, lo, hi, distinct_detector_count(findings), len(findings), lang)
    _render_footer_hints(console, lang)


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
    counts.add_row("NEW", Text(str(len(diff.new)), style="bold red" if diff.new else "bold"))
    counts.add_row("RESOLVED", Text(str(len(diff.resolved)), style="bold green"))
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
        new_list.append(i18n.t(lang, "new_findings_label"), style="bold red")
        for f in diff.new:
            new_list.append(f"  • {f.object_name}", style="bold")
            new_list.append(f"  [{f.detector}]  {f.snippet}\n", style="dim")
        parts.append(new_list)

    console.print(
        Panel(
            Group(*parts),
            title=i18n.t(lang, "baseline_panel_title"),
            title_align="left",
            border_style="magenta",
        )
    )


def _render_banner(console: Console) -> None:
    banner = Text(justify="center")
    banner.append("ORACLE → POSTGRESQL MIGRATION GAP REPORT\n", style="bold")
    banner.append("ora2pg-gap-report", style="dim")
    console.print(Panel(banner, border_style="blue"))


def _render_run_info(
    console: Console,
    finding_count: int,
    objects_scanned: int | None,
    elapsed_seconds: float | None,
    lang: str = "ru",
) -> None:
    info = Table.grid(padding=(0, 2))
    info.add_column(style="dim")
    info.add_column()
    if objects_scanned is not None:
        info.add_row(i18n.t(lang, "run_info_objects_scanned"), Text(str(objects_scanned), style="bold"))
    info.add_row(i18n.t(lang, "run_info_findings_found"), Text(str(finding_count), style="bold"))
    if elapsed_seconds is not None:
        info.add_row(
            i18n.t(lang, "run_info_elapsed"),
            Text(i18n.t(lang, "elapsed_value", s=elapsed_seconds), style="dim"),
        )
    console.print(Panel(info, border_style="cyan"))


def _render_findings_summary(console: Console, counts: dict[str, int], lang: str = "ru") -> None:
    body = Text()
    for i, (name, n) in enumerate(ordered_counts(counts)):
        if i:
            body.append("\n")
        style = _SEVERITY_STYLE.get(name)
        body.append(f"{_severity_dot(name)} ", style=style)
        body.append(f"{name.upper():<8}", style=style)
        body.append(str(n), style=style)
    console.print(
        Panel(body, title=i18n.t(lang, "severity_panel_title"), title_align="left", border_style="cyan")
    )


def _render_effort_panel(
    console: Console,
    lo: float,
    hi: float,
    distinct_patterns: int,
    total_findings: int,
    lang: str = "ru",
) -> None:
    mid = (lo + hi) / 2
    rows = Table.grid(padding=(0, 2))
    rows.add_column(style="dim")
    rows.add_column()
    rows.add_row(i18n.t(lang, "effort_best"), Text(i18n.t(lang, "hours_value", v=lo), style="bold"))
    rows.add_row(i18n.t(lang, "effort_avg"), Text(i18n.t(lang, "hours_value", v=mid), style="bold"))
    rows.add_row(i18n.t(lang, "effort_worst"), Text(i18n.t(lang, "hours_value", v=hi), style="bold"))

    body = Text()
    body.append(i18n.t(lang, "effort_disclaimer"), style="dim")
    if distinct_patterns < total_findings:
        body.append("\n")
        body.append(
            i18n.t(lang, "effort_patterns_note", patterns=distinct_patterns, findings=total_findings),
            style="dim",
        )

    group = Group(rows, Text(), body)
    console.print(
        Panel(group, title=i18n.t(lang, "effort_panel_title"), title_align="left", border_style="blue")
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


def _render_recommended_actions(findings: list[Finding], console: Console, lang: str = "ru") -> None:
    """One line per detector actually present, count first — a compact
    index into the "Пояснения" section below, not new analysis. Ordered by
    how many findings each detector produced, worst first."""
    by_detector: dict[str, int] = {}
    for f in findings:
        by_detector[f.detector] = by_detector.get(f.detector, 0) + 1

    ranked = sorted(by_detector.items(), key=lambda kv: -kv[1])
    hints = REMEDIATION_HINT_EN if lang == "en" else _REMEDIATION_HINT

    body = Text()
    for i, (detector, n) in enumerate(ranked, start=1):
        if i > 1:
            body.append("\n\n")
        body.append(f"[{i}] ", style="bold")
        body.append(f"{detector}  ")
        body.append(f"({n})\n", style="dim")
        hint = hints.get(detector, i18n.t(lang, "see_explanation_below"))
        body.append(f"    → {hint}", style="dim")

    console.print(
        Panel(body, title=i18n.t(lang, "recommendations_panel_title"), title_align="left", border_style="magenta")
    )


def _render_top_objects(findings: list[Finding], console: Console, lang: str = "ru") -> None:
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

    tree = Tree(Text(i18n.t(lang, "top_objects_tree_title"), style="bold"))
    for object_name, group in ranked[:_TOP_OBJECTS_LIMIT]:
        by_detector: dict[str, list[Finding]] = {}
        for f in group:
            by_detector.setdefault(f.detector, []).append(f)

        branch_label = Text()
        branch_label.append(object_name, style="bold")
        branch_label.append(i18n.t(lang, "findings_count_suffix", n=len(group)))
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
        tree.add(Text(i18n.t(lang, "and_more_objects", n=remaining), style="dim"))

    console.print(tree)
    console.print()


_VERIFICATION_STATUS_STYLE = {
    "still_present": "bold red",
    "not_detected": "bold green",
    "not_verifiable": "dim",
}


def render_verification(
    results: list[DetectorVerification], console: Console | None = None, lang: str = "ru"
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
    _render_banner(console)

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
    console.print(Panel(summary, title=i18n.t(lang, "verify_panel_title"), title_align="left", border_style="cyan"))

    if not results:
        return

    table = Table(show_lines=True, expand=True)
    table.add_column(i18n.t(lang, "verify_col_detector"), style="magenta", no_wrap=True, overflow="ellipsis")
    table.add_column(i18n.t(lang, "verify_col_gap"), width=9)
    table.add_column(i18n.t(lang, "verify_col_before"), justify="right", width=12)
    table.add_column(i18n.t(lang, "verify_col_after"), justify="right", width=12)
    table.add_column(i18n.t(lang, "verify_col_status"), width=16)

    for r in results:
        status_style = _VERIFICATION_STATUS_STYLE.get(r.status)
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
