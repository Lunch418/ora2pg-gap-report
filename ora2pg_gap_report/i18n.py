"""Output language for the CLI: resolution order, persistence, and the
English strings themselves.

Scope, deliberately: this covers everything a normal scan run prints —
terminal_report.py's rendered output, report_generator.py's Markdown/HTML
headers, cli.py's runtime warnings/errors, baseline.py's load errors, every
detector's explanation/remediation text, argparse's own --help/description
text (cli.py's _peek_lang_for_help() resolves the display language *before*
argparse has parsed --lang out of argv -- the chicken-and-egg this docstring
used to flag as unsolved), and tui_app.py's own chrome (button labels,
status/error text, table headers -- GapReportApp/run_tui() take a `lang`
threaded in from the CLI's own resolved language). It does NOT cover
oracle_export.py/oracle_connector.py's messages (a separate console entry
point, live-Oracle-only, out of scope for this pass) -- that boundary is
intentional, not an oversight -- see CHANGELOG.md.

Russian stays the silent default when nothing selects a language, so every
existing script/CI config that parses this tool's Russian output keeps
working unchanged. English is opt-in: --lang en for one run, --set-lang to
persist a choice, ORA2PG_GAP_REPORT_LANG=en for CI, or (only when running
interactively with nothing configured yet) a one-time picker on first run.

EXPLANATION_EN is keyed by the exact Russian message text (not by detector
name) because a handful of detectors emit more than one distinct message
(bulk_collect has three) -- keying by the message itself, which is exactly
what Finding.message already holds, gives an unambiguous lookup with no
detector-specific plumbing. scripts/doctor.py cross-checks this dict
against every detector's message constants on disk, the same drift-
prevention pattern as its other parity checks.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

Lang = str  # "ru" | "en"

_LANGUAGES = ("ru", "en")
_ENV_VAR = "ORA2PG_GAP_REPORT_LANG"


def _config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    return Path(base) / "ora2pg-gap-report" if base else Path.home() / ".config" / "ora2pg-gap-report"


def _config_file() -> Path:
    return _config_dir() / "language"


def get_saved_language() -> str | None:
    try:
        value = _config_file().read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value if value in _LANGUAGES else None


def save_language(lang: str) -> None:
    config_dir = _config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    _config_file().write_text(lang, encoding="utf-8")


def prompt_language_interactively(console: Console | None = None) -> str:
    """A short, bilingual picker -- readable regardless of which language
    the user already reads, since at this point we don't know yet.

    Imports rich lazily, here and not at module level: this module is
    imported by report_generator.py/baseline.py, which the project's own
    pyproject.toml/README both describe as not depending on rich at all
    -- a module-level `from rich... import ...` here would make that
    false for every caller, not just the one (--set-lang) that actually
    needs a console picker."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.text import Text

    console = console or Console()
    console.print(
        Panel(
            Text("[1] English\n[2] Русский", justify="left"),
            title="Choose a language / Выберите язык",
            title_align="left",
            border_style="cyan",
        )
    )
    choice = Prompt.ask("Your choice / Ваш выбор", choices=["1", "2"], default="1", console=console)
    return "en" if choice == "1" else "ru"


def resolve_language(explicit: str | None, *, interactive: bool) -> str:
    """Resolution order: --lang (this run only) > ORA2PG_GAP_REPORT_LANG
    env var (for CI, doesn't persist) > a previously saved --set-lang
    choice > (interactive terminal, nothing configured yet) a one-time
    picker whose result gets saved > "ru", unchanged from before this
    module existed."""
    if explicit in _LANGUAGES:
        return explicit

    env = os.environ.get(_ENV_VAR)
    if env in _LANGUAGES:
        return env

    saved = get_saved_language()
    if saved is not None:
        return saved

    if interactive:
        chosen = prompt_language_interactively()
        save_language(chosen)
        return chosen

    return "ru"


def t(lang: str, key: str, **kwargs: object) -> str:
    entry = _UI.get(key)
    if entry is None:
        raise KeyError(f"no i18n UI string registered for key {key!r}")
    template = entry.get(lang, entry["ru"])
    return template.format(**kwargs) if kwargs else template


# UI strings used by terminal_report.py, cli.py's runtime messages, and
# report_generator.py's Markdown/HTML headers. Grouped roughly by where
# each one is used, not alphabetically -- easier to audit against the
# rendering code that consumes it.
_UI: dict[str, dict[str, str]] = {
    # terminal_report.py
    "no_findings": {"ru": "Проблемных конструкций не найдено.", "en": "No problematic constructs found."},
    "objects_scanned_inline": {"ru": "\nОбъектов просканировано: {n}", "en": "\nObjects scanned: {n}"},
    "elapsed_inline": {"ru": "\nВремя анализа: {s:.1f} с", "en": "\nAnalysis time: {s:.1f}s"},
    "all_findings_title": {"ru": "Все находки", "en": "All findings"},
    "col_file": {"ru": "Файл", "en": "File"},
    "col_object": {"ru": "Объект", "en": "Object"},
    "col_line": {"ru": "Строка", "en": "Line"},
    "col_severity": {"ru": "Severity", "en": "Severity"},
    "col_detector": {"ru": "Детектор", "en": "Detector"},
    "col_snippet": {"ru": "Фрагмент", "en": "Snippet"},
    "explanations_title": {"ru": "Пояснения", "en": "Explanations"},
    "explanation_panel_title": {"ru": "{detector} — {n} объект(ов)", "en": "{detector} — {n} object(s)"},
    "run_info_objects_scanned": {"ru": "Объектов просканировано", "en": "Objects scanned"},
    "run_info_findings_found": {"ru": "Найдено проблемных объектов", "en": "Problematic objects found"},
    "run_info_elapsed": {"ru": "Время анализа", "en": "Analysis time"},
    "elapsed_value": {"ru": "{s:.1f} с", "en": "{s:.1f}s"},
    "severity_panel_title": {"ru": "Находки по severity", "en": "Findings by severity"},
    "effort_best": {"ru": "Лучший случай", "en": "Best case"},
    "effort_avg": {"ru": "Среднее", "en": "Average"},
    "effort_worst": {"ru": "Худший случай", "en": "Worst case"},
    "hours_value": {"ru": "{v:g} ч", "en": "{v:g}h"},
    "effort_disclaimer": {
        "ru": "— неоткалиброванная эвристика по severity, не измерение",
        "en": "— an uncalibrated heuristic based on severity, not a measurement",
    },
    "effort_patterns_note": {
        "ru": "{patterns} паттернов из {findings} находок — первое вхождение паттерна "
        "оценивается по полной стоимости, повторные — дешевле (тот же фикс, "
        "применённый ещё раз, не новая задача)",
        "en": "{patterns} patterns behind {findings} findings — a pattern's first "
        "occurrence is priced in full, repeats are cheaper (the same fix applied "
        "again, not a new problem)",
    },
    "effort_panel_title": {"ru": "Оценка ручной доработки", "en": "Manual rework estimate"},
    "footer_hint_severity_label": {
        "ru": "Показать только высокую критичность:",
        "en": "Show only high severity:",
    },
    "footer_hint_object_label": {
        "ru": "Сфокусироваться на одном объекте:    ",
        "en": "Focus on a single object:            ",
    },
    "recommendations_panel_title": {"ru": "Рекомендации", "en": "Recommendations"},
    "see_explanation_below": {"ru": "См. пояснение ниже.", "en": "See the explanation below."},
    "top_objects_tree_title": {
        "ru": "Объекты с наибольшим числом находок",
        "en": "Objects with the most findings",
    },
    "findings_count_suffix": {"ru": "  {n} находок", "en": "  {n} findings"},
    "and_more_objects": {"ru": "… и ещё {n} объект(ов)", "en": "… and {n} more object(s)"},
    "baseline_panel_title": {"ru": "Сравнение с baseline", "en": "Baseline comparison"},
    "new_findings_label": {"ru": "Новые находки:\n", "en": "New findings:\n"},
    # cli.py runtime messages
    "explain_unknown_gap": {
        "ru": "[red]Неизвестный GAP: {ref}[/red] — ожидается номер из "
        "docs/research/GAP_REGISTRY.md, например GAP-023 или 023",
        "en": "[red]Unknown GAP: {ref}[/red] — expected a number from "
        "docs/research/GAP_REGISTRY.md, e.g. GAP-023 or 023",
    },
    "confirmed_versions": {
        "ru": "Подтверждено на: ora2pg {ora2pg_version}, PostgreSQL {postgresql_version}",
        "en": "Confirmed on: ora2pg {ora2pg_version}, PostgreSQL {postgresql_version}",
    },
    "explain_failure_stage_line": {"ru": "Когда ломается: {stage}", "en": "Fails at: {stage}"},
    "failure_stage_conversion": {
        "ru": "конвертация — видно только в собственном логе прогона ora2pg "
        "(DEBUG-строка или пропущенный/недосчитанный объект), ещё до PostgreSQL",
        "en": "conversion — only visible in ora2pg's own conversion run/log "
        "(a debug line, or an omitted/undercounted object), before PostgreSQL is involved at all",
    },
    "failure_stage_deployment": {
        "ru": "развёртывание — сгенерированный DDL сразу падает при загрузке в PostgreSQL",
        "en": "deployment — the generated DDL fails to load into PostgreSQL, immediately",
    },
    "failure_stage_runtime": {
        "ru": "выполнение — DDL загружается без ошибок (в дампе ora2pg заранее стоит "
        "check_function_bodies = false), но помеченный код падает при первом реальном вызове",
        "en": "runtime — the DDL loads cleanly (ora2pg's own dump sets "
        "check_function_bodies = false), but the flagged code fails the first time it actually runs",
    },
    "failure_stage_semantic": {
        "ru": "тихая потеря поведения — ошибки не будет никогда, ни на одном этапе; "
        "поведение просто тихо отличается от Oracle, пока кто-то специально не проверит",
        "en": "silent behavior loss — no error is ever raised, at any stage; behavior is just "
        "silently different from Oracle, unless someone specifically checks for it",
    },
    # Compact one/two-word versions of the four failure_stage_* strings
    # above, for places that show a gap's stage next to many findings at
    # once (the main report's per-detector explanation panel, and the
    # markdown/html/csv table columns) where the full explanatory sentence
    # would be too wide to repeat -- the long form stays reserved for
    # --explain, where there's room and it's the only thing on the line.
    "failure_stage_short_conversion": {"ru": "конвертация", "en": "conversion"},
    "failure_stage_short_deployment": {"ru": "развёртывание", "en": "deployment"},
    "failure_stage_short_runtime": {"ru": "выполнение", "en": "runtime"},
    "failure_stage_short_semantic": {"ru": "тихая потеря поведения", "en": "silent behavior loss"},
    "explanation_gap_stage_line": {"ru": "{gap} · Когда ломается: {stage}", "en": "{gap} · Fails at: {stage}"},
    "explain_doc_not_local": {
        "ru": "[yellow]GAP-{number} ({detector}): research-документ не найден локально[/yellow] "
        "(research-документы не входят в pip-пакет — это репозиторий, а не установленный CLI).",
        "en": "[yellow]GAP-{number} ({detector}): research doc not found locally[/yellow] "
        "(research docs aren't shipped in the pip package — that's the repository, not the "
        "installed CLI).",
    },
    "explain_see_github": {"ru": "Смотреть на GitHub: {url}", "en": "See it on GitHub: {url}"},
    "explain_conflict_error": {
        "ru": "[red]--explain — самостоятельный просмотр документации, не сканирование: "
        "его нельзя сочетать с путями к файлам, --fail-on, --save, --baseline, "
        "--check-connect-by, --verify, --format, --output, --severity или --object[/red]",
        "en": "[red]--explain is a standalone documentation lookup, not a scan: it can't be "
        "combined with file paths, --fail-on, --save, --baseline, --check-connect-by, "
        "--verify, --format, --output, --severity, or --object[/red]",
    },
    "tui_conflict_error": {
        "ru": "[red]--tui — самостоятельный интерактивный режим: принимает не больше одного "
        "пути (стартовая точка в дереве) и не сочетается с --explain, --verify, --fail-on, "
        "--save, --baseline, --check-connect-by, --severity, --object, --format или "
        "--output[/red]",
        "en": "[red]--tui is a standalone interactive mode: it takes at most one path (a "
        "starting point for the tree) and can't be combined with --explain, --verify, "
        "--fail-on, --save, --baseline, --check-connect-by, --severity, --object, --format, "
        "or --output[/red]",
    },
    "tui_not_installed": {
        "ru": "[red]--tui требует пакет textual, который не установлен.[/red] "
        "Поставьте его: pip install \"ora2pg-gap-report[tui]\"",
        "en": "[red]--tui requires the textual package, which isn't installed.[/red] "
        "Install it: pip install \"ora2pg-gap-report[tui]\"",
    },
    "no_paths_error": {
        "ru": "[red]Нужно указать хотя бы один файл/директорию, либо --explain GAP-NNN[/red]",
        "en": "[red]Specify at least one file/directory, or --explain GAP-NNN[/red]",
    },
    "empty_dir_warning": {
        "ru": "[yellow]Директория не содержит .sql/.pks/.pkb файлов:[/yellow] {dir}",
        "en": "[yellow]Directory has no .sql/.pks/.pkb files:[/yellow] {dir}",
    },
    "skipped_not_found": {
        "ru": "[yellow]Пропущен (не найден):[/yellow] {path}",
        "en": "[yellow]Skipped (not found):[/yellow] {path}",
    },
    "skipped_unreadable": {
        "ru": "[yellow]Пропущен (не читается: {exc}):[/yellow] {path}",
        "en": "[yellow]Skipped (unreadable: {exc}):[/yellow] {path}",
    },
    "connect_by_not_found": {
        "ru": "{path}: содержит CONNECT BY, но ora2pg не найден — проверка пропущена",
        "en": "{path}: contains CONNECT BY, but ora2pg wasn't found — check skipped",
    },
    "connect_by_run_error": {
        "ru": "{path}: содержит CONNECT BY, но запуск ora2pg завершился ошибкой ({exc})",
        "en": "{path}: contains CONNECT BY, but running ora2pg failed ({exc})",
    },
    "save_baseline_error": {
        "ru": "[red]Не удалось сохранить baseline в {path}: {exc}[/red]",
        "en": "[red]Couldn't save baseline to {path}: {exc}[/red]",
    },
    "save_baseline_same_path_error": {
        "ru": "[red]--save и --baseline указывают на один и тот же файл ({path}) — сравнение "
        "прогона с самим собой всегда покажет «без изменений». Используйте разные пути: "
        "--baseline на старый снапшот, --save на новый.[/red]",
        "en": "[red]--save and --baseline point at the same file ({path}) — comparing this run "
        "against itself always reports \"unchanged\". Use different paths: --baseline for the "
        "old snapshot, --save for the new one.[/red]",
    },
    "save_baseline_skipped_partial_scan": {
        "ru": "[yellow]baseline не сохранён в {path}: сканирование было неполным (см. "
        "предупреждения выше) — снапшот с пропущенными файлами не запишется как «полный»[/yellow]",
        "en": "[yellow]baseline not saved to {path}: the scan was incomplete (see warnings "
        "above) — a snapshot with skipped files won't be written as though it were complete[/yellow]",
    },
    "write_report_error": {
        "ru": "[red]Не удалось записать отчёт в {path}: {exc}[/red]",
        "en": "[red]Couldn't write the report to {path}: {exc}[/red]",
    },
    "gate_failed": {
        "ru": "\n[bold red]Migration gate FAILED[/bold red] — {n} находок с "
        "severity {sev} и выше (порог --fail-on {sev})",
        "en": "\n[bold red]Migration gate FAILED[/bold red] — {n} findings at "
        "severity {sev} or higher (--fail-on {sev} threshold)",
    },
    "lang_saved": {
        "ru": "Сохранено: {chosen}. Изменить снова: --set-lang.",
        "en": "Saved: {chosen}. Change it again anytime with --set-lang.",
    },
    # --verify (post-migration static verification)
    "verify_requires_baseline": {
        "ru": "[red]--verify требует --baseline PATH — снапшот, сохранённый через --save "
        "до миграции[/red]",
        "en": "[red]--verify requires --baseline PATH — a snapshot saved via --save "
        "before the migration[/red]",
    },
    "verify_conflict_error": {
        "ru": "[red]--verify — отдельный режим сравнения с baseline, его нельзя сочетать "
        "с --explain, --save, --fail-on, --check-connect-by, --severity или --object[/red]",
        "en": "[red]--verify is a standalone baseline-comparison mode, it can't be "
        "combined with --explain, --save, --fail-on, --check-connect-by, --severity, "
        "or --object[/red]",
    },
    "verify_unsupported_format": {
        "ru": "[red]--verify поддерживает только --format terminal и --format json[/red]",
        "en": "[red]--verify only supports --format terminal and --format json[/red]",
    },
    "verify_panel_title": {
        "ru": "Проверка после миграции",
        "en": "Post-migration verification",
    },
    "verify_summary_baseline_detectors": {
        "ru": "Детекторов в baseline",
        "en": "Baseline detectors",
    },
    "verify_summary_still_present": {"ru": "Осталось", "en": "Still present"},
    "verify_summary_not_detected": {"ru": "Не обнаружено", "en": "Not detected"},
    "verify_summary_not_verifiable": {"ru": "Нельзя проверить", "en": "Not verifiable"},
    "verify_col_detector": {"ru": "Детектор", "en": "Detector"},
    "verify_col_gap": {"ru": "GAP", "en": "GAP"},
    "verify_col_before": {"ru": "До миграции", "en": "Before"},
    "verify_col_after": {"ru": "После миграции", "en": "After"},
    "verify_col_status": {"ru": "Статус", "en": "Status"},
    "verify_footer_note": {
        "ru": "NOT_DETECTED означает «в проверенном коде паттерн не нашёлся», а не "
        "«проблема доказанно исправлена» — см. docs/ARCHITECTURE.md. NOT_VERIFIABLE — "
        "ora2pg отбрасывает эту конструкцию из вывода на любой миграции, повторный "
        "прогон детектора здесь ничего не доказывает в принципе.",
        "en": "NOT_DETECTED means \"the pattern wasn't found in the checked code\", not "
        "\"the problem is provably fixed\" — see docs/ARCHITECTURE.md. NOT_VERIFIABLE — "
        "ora2pg drops this construct from its output on every migration, so re-running "
        "the detector here can't prove anything either way.",
    },
    "set_lang_not_interactive": {
        "ru": "[red]--set-lang открывает интерактивный выбор языка — нужен настоящий "
        "терминал. Используйте --lang ru|en для одного запуска или "
        "ORA2PG_GAP_REPORT_LANG=ru|en.[/red]",
        "en": "[red]--set-lang opens an interactive language picker — it needs a real "
        "terminal. Use --lang ru|en for a single run, or "
        "ORA2PG_GAP_REPORT_LANG=ru|en.[/red]",
    },
    # baseline.py load errors
    "baseline_unreadable": {
        "ru": "{path}: не удалось прочитать ({exc})",
        "en": "{path}: couldn't be read ({exc})",
    },
    "baseline_not_utf8": {
        "ru": "{path}: не в кодировке UTF-8 ({exc})",
        "en": "{path}: not UTF-8 encoded ({exc})",
    },
    "baseline_not_json": {"ru": "{path}: не похоже на JSON ({exc})", "en": "{path}: doesn't look like JSON ({exc})"},
    "baseline_no_findings_key": {
        "ru": "{path}: не похоже на baseline-файл ora2pg-gap-report (нет списка 'findings')",
        "en": "{path}: doesn't look like an ora2pg-gap-report baseline file (no 'findings' list)",
    },
    "baseline_schema_mismatch": {
        "ru": "{path}: schema_version={schema_version!r}, эта версия инструмента "
        "ожидает {expected} — пересохраните baseline через --save текущей версией",
        "en": "{path}: schema_version={schema_version!r}, this version of the tool "
        "expects {expected} — re-save the baseline with --save using the current version",
    },
    "baseline_missing_field": {
        "ru": "{path}: запись находки без обязательного поля/полей: {field}",
        "en": "{path}: a finding entry is missing required field(s): {field}",
    },
    # report_generator.py (to_markdown / to_html)
    "md_no_findings": {"ru": "Проблемных конструкций не найдено.\n", "en": "No problematic constructs found.\n"},
    "md_table_header": {
        "ru": "| Файл | Объект | Строка | Серьёзность | Фрагмент | Комментарий | GAP | Когда ломается |",
        "en": "| File | Object | Line | Severity | Snippet | Comment | GAP | Fails at |",
    },
    "html_table_header": {
        "ru": "<th>Файл</th><th>Объект</th><th>Строка</th><th>Серьёзность</th>"
        "<th>Фрагмент</th><th>Комментарий</th><th>GAP</th><th>Когда ломается</th>",
        "en": "<th>File</th><th>Object</th><th>Line</th><th>Severity</th>"
        "<th>Snippet</th><th>Comment</th><th>GAP</th><th>Fails at</th>",
    },
    "html_no_findings": {
        "ru": '<p class="empty">Проблемных конструкций не найдено.</p>',
        "en": '<p class="empty">No problematic constructs found.</p>',
    },
    "html_title": {"ru": "Отчёт ora2pg-gap-report", "en": "ora2pg-gap-report report"},
    "html_h1": {"ru": "Отчёт ora2pg-gap-report", "en": "ora2pg-gap-report report"},
    "html_findings_found": {
        "ru": "Найдено проблемных объектов: {n} ({counts})",
        "en": "Problematic objects found: {n} ({counts})",
    },
    "html_effort_caveat": {
        "ru": "Грубая оценка ручной доработки: {lo:g}–{hi:g} ч. — неоткалиброванная эвристика "
        "по severity, не измерение (см. README.md, «Почему почти всё high»).",
        "en": "Rough manual-rework estimate: {lo:g}–{hi:g}h. — an uncalibrated heuristic based "
        "on severity, not a measurement (see README.md, \"Why almost everything is "
        "`high`\").",
    },
    "markdown_report_title": {"ru": "# Отчёт ora2pg-gap-report\n\n", "en": "# ora2pg-gap-report report\n\n"},
    "markdown_findings_found": {
        "ru": "Найдено проблемных объектов: {n} ({counts})\n\n",
        "en": "Problematic objects found: {n} ({counts})\n\n",
    },
    "markdown_effort_estimate": {
        "ru": "Грубая оценка ручной доработки: {lo:g}–{hi:g} ч. "
        "— неоткалиброванная эвристика по severity, не измерение "
        "(см. README.md, «Почему почти всё high»).\n\n",
        "en": "Rough manual-rework estimate: {lo:g}–{hi:g}h. "
        "— an uncalibrated heuristic based on severity, not a measurement "
        "(see README.md, \"Why almost everything is `high`\").\n\n",
    },
    # cli.py argparse --help/description text. Resolved *before* argparse
    # actually parses argv (see cli.py's _peek_lang_for_help()) -- the
    # classic chicken-and-egg this module's own docstring used to flag as
    # unsolved: argparse needs a fully-built parser (help text included) to
    # parse --lang out of argv, but building translated help text needs to
    # already know --lang.
    "help_description": {
        "ru": "Сканирует выгруженный Oracle DDL (PACKAGE BODY / TRIGGER) и "
        "показывает конкретные объекты, которые ora2pg не перенесёт "
        "корректно, и почему.",
        "en": "Scans exported Oracle DDL (PACKAGE BODY / TRIGGER) and shows the "
        "specific objects ora2pg won't migrate correctly, and why.",
    },
    "help_paths": {
        "ru": "Файлы с DDL для анализа (.sql/.pks/.pkb) и/или директории — "
        "директория сканируется рекурсивно на файлы с этими "
        "расширениями. Не нужны вместе с --explain.",
        "en": "DDL files to analyze (.sql/.pks/.pkb) and/or directories — a "
        "directory is scanned recursively for files with these "
        "extensions. Not needed together with --explain.",
    },
    "help_version": {"ru": "Показать установленную версию и выйти", "en": "Show the installed version and exit"},
    "help_explain": {
        "ru": "Показать research-документ конкретного gap'а из реестра (например, GAP-023 или "
        "просто 023) и выйти — без сканирования файлов. Самостоятельная команда: нельзя "
        "сочетать с путями к файлам, --fail-on, --save, --baseline, --check-connect-by, "
        "--verify, --format, --output, --severity или --object.",
        "en": "Show a specific gap's research document from the registry (e.g. GAP-023 or "
        "just 023) and exit — no file scanning. A standalone command: can't be combined "
        "with file paths, --fail-on, --save, --baseline, --check-connect-by, --verify, "
        "--format, --output, --severity, or --object.",
    },
    "help_format": {
        "ru": "Формат отчёта. По умолчанию — цветной вывод в терминал, если "
        "stdout это tty и не указан --output; иначе markdown. sarif — "
        "SARIF 2.1.0, для GitHub/GitLab code scanning. html — "
        "самодостаточная HTML-страница (без внешних ресурсов), для "
        "показа заказчику/руководству.",
        "en": "Report format. Defaults to colored terminal output if stdout is a "
        "tty and --output isn't given; markdown otherwise. sarif — SARIF "
        "2.1.0, for GitHub/GitLab code scanning. html — a self-contained "
        "HTML page (no external resources), for showing a client/manager.",
    },
    "help_output": {"ru": "Куда сохранить отчёт (по умолчанию — stdout)", "en": "Where to save the report (default: stdout)"},
    "help_check_connect_by": {
        "ru": "Дополнительно: для файлов с CONNECT BY реально прогнать ora2pg и "
        "проверить сгенерированный WITH RECURSIVE на известный баг с LEVEL. "
        "Требует установленный ora2pg (не ставится через pip — это "
        "отдельный Perl-инструмент, см. README).",
        "en": "Extra: for files with CONNECT BY, actually run ora2pg and check "
        "the generated WITH RECURSIVE for a known bug with LEVEL. Requires "
        "ora2pg installed (not a pip package — a separate Perl tool, see "
        "README).",
    },
    "help_ora2pg_bin": {
        "ru": "Путь к исполняемому файлу ora2pg (по умолчанию ищется в PATH)",
        "en": "Path to the ora2pg executable (default: looked up on PATH)",
    },
    "help_severity": {
        "ru": "Показать только находки с этим уровнем серьёзности",
        "en": "Show only findings at this severity level",
    },
    "help_object": {
        "ru": "Показать только находки для объектов, чьё имя содержит эту подстроку (без учёта регистра)",
        "en": "Show only findings for objects whose name contains this substring (case-insensitive)",
    },
    "help_save": {
        "ru": "Сохранить находки этого прогона как baseline-снапшот в PATH (для последующего "
        "сравнения через --baseline). Снапшот — все находки, независимо от --severity/--object; "
        "эти флаги влияют только на то, что выводится в отчёте.",
        "en": "Save this run's findings as a baseline snapshot at PATH (for a later comparison "
        "via --baseline). The snapshot holds every finding regardless of --severity/--object; "
        "those flags only affect what the report shows.",
    },
    "help_baseline": {
        "ru": "Сравнить находки этого прогона с ранее сохранённым --save снапшотом: NEW/RESOLVED/"
        "UNCHANGED. Сравнение тоже считается по всем находкам, независимо от --severity/--object. "
        "С флагом --verify означает другое — см. --verify.",
        "en": "Compare this run's findings against a previously saved --save snapshot: NEW/"
        "RESOLVED/UNCHANGED. The comparison also covers every finding regardless of "
        "--severity/--object. Means something different together with --verify — see --verify.",
    },
    "help_verify": {
        "ru": "Пост-миграционная статическая проверка: сканирует пути как сгенерированный ora2pg "
        "PostgreSQL-код (не Oracle-исходник) и сравнивает с --baseline (снапшот, сохранённый "
        "--save до миграции) на уровне детекторов — STILL_PRESENT/NOT_DETECTED/NOT_VERIFIABLE. "
        "Не поведенческая/функциональная проверка — не подключается к БД, ничего не выполняет. "
        "Требует --baseline. Самостоятельный режим: нельзя сочетать с --explain, --save, "
        "--fail-on, --check-connect-by, --severity или --object. Поддерживает только "
        "--format terminal (по умолчанию) и --format json.",
        "en": "Post-migration static check: scans the given paths as ora2pg's generated "
        "PostgreSQL code (not Oracle source) and compares them against --baseline (a "
        "snapshot saved via --save before migrating) at the detector level — "
        "STILL_PRESENT/NOT_DETECTED/NOT_VERIFIABLE. Not a behavioral/functional check — "
        "doesn't connect to a database or run anything. Requires --baseline. A standalone "
        "mode: can't be combined with --explain, --save, --fail-on, --check-connect-by, "
        "--severity, or --object. Only supports --format terminal (default) and --format "
        "json.",
    },
    "help_fail_on": {
        "ru": "Завершиться с кодом 1, если среди находок есть хотя бы одна с этим уровнем серьёзности "
        "или выше (high выше medium выше low) — для CI-гейта. Оценивается по всем находкам, "
        "независимо от --severity/--object, чтобы фильтр вывода не маскировал провал гейта.",
        "en": "Exit with code 1 if any finding is at this severity level or above (high above "
        "medium above low) — for a CI gate. Evaluated over every finding regardless of "
        "--severity/--object, so an output filter can't mask a failed gate.",
    },
    "help_lang": {
        "ru": "Язык вывода для этого запуска (не сохраняется). По умолчанию: сохранённый через "
        "--set-lang выбор, иначе переменная окружения ORA2PG_GAP_REPORT_LANG, иначе "
        "интерактивный выбор при первом запуске в реальном терминале, иначе русский.",
        "en": "Output language for this run (not persisted). Defaults to: a choice saved via "
        "--set-lang, else the ORA2PG_GAP_REPORT_LANG environment variable, else an "
        "interactive picker on first run in a real terminal, else Russian.",
    },
    "help_set_lang": {
        "ru": "Открыть выбор языка и сохранить его как язык по умолчанию для будущих запросов, затем выйти.",
        "en": "Open the language picker and save the choice as the default for future runs, then exit.",
    },
    "help_tui": {
        "ru": "Интерактивный режим: выбор файла/директории и запуск сканирования мышью или "
        "клавиатурой вместо флагов. Требует textual (pip install \"ora2pg-gap-report[tui]\"), "
        "не ставится вместе с базовым пакетом. Если указан один путь-директория — она "
        "открывается как стартовая точка в дереве; самостоятельный режим, как --explain/"
        "--verify — не сочетается с --fail-on/--save/--baseline/--check-connect-by/--explain/"
        "--verify/--severity/--object/--format/--output.",
        "en": "Interactive mode: pick a file/directory and run a scan with the mouse or "
        "keyboard instead of flags. Requires textual (pip install "
        "\"ora2pg-gap-report[tui]\"), not installed with the base package. If a single "
        "directory path is given, it opens as the tree's starting point; a standalone "
        "mode, like --explain/--verify — not combinable with --fail-on/--save/--baseline/"
        "--check-connect-by/--explain/--verify/--severity/--object/--format/--output.",
    },
    # tui_app.py (--tui) chrome -- everything the interactive mode's own
    # screens show (button labels, status/error text, table headers) that
    # isn't already scanned-detector content (that part was already
    # routed through this module's other keys, e.g. failure_stage_short_*
    # in ResultsScreen's detail panel). Reuses col_*/verify_col_*/
    # verify_footer_note directly rather than duplicating them under a
    # tui_ prefix -- same words, same screen concept (a findings table / a
    # verification table), just rendered by Textual instead of Rich.
    "tui_app_subtitle": {
        "ru": "Отчёт о пробелах миграции Oracle -> PostgreSQL",
        "en": "Oracle -> PostgreSQL migration gap report",
    },
    "tui_tree_label": {
        "ru": "Выберите файл .sql/.pks/.pkb или директорию для рекурсивного сканирования:",
        "en": "Pick a .sql/.pks/.pkb file, or a directory to scan recursively:",
    },
    "tui_severity_all": {"ru": "Все уровни", "en": "All severities"},
    # {level} is deliberately not translated -- "high"/"medium"/"low" are
    # kept as fixed technical vocabulary everywhere else in this project
    # (--severity's own choices, col_severity's "Severity" header even in
    # Russian, terminal_report.py's NEW/RESOLVED/UNCHANGED), not prose.
    "tui_severity_only": {"ru": "Только {level}", "en": "{level} only"},
    "tui_scan_btn": {"ru": "Сканировать", "en": "Scan"},
    "tui_add_to_selection_btn": {"ru": "Добавить к выбору", "en": "Add to selection"},
    "tui_clear_selection_btn": {"ru": "Очистить выбор", "en": "Clear selection"},
    "tui_connect_by_checkbox": {
        "ru": "Проверить CONNECT BY (требует ora2pg)",
        "en": "Check CONNECT BY (requires ora2pg)",
    },
    "tui_baseline_input_placeholder": {
        "ru": "Файл baseline (опционально — сравнить или сверить с ним)",
        "en": "Baseline file (optional -- compare or verify against it)",
    },
    "tui_verify_checkbox": {
        "ru": "Режим verify (сканировать как результат после миграции)",
        "en": "Verify mode (scan as post-migration output)",
    },
    "tui_status_nothing_selected": {"ru": "Пока ничего не выбрано.", "en": "Nothing selected yet."},
    "tui_status_highlighted": {"ru": "Выделено: {path}", "en": "Highlighted: {path}"},
    "tui_status_queued": {
        "ru": "Путей в очереди на сканирование: {n}\n{listing}",
        "en": "{n} path(s) queued for scan:\n{listing}",
    },
    "tui_error_pick_in_tree_first": {
        "ru": "Сначала выберите файл или директорию в дереве.",
        "en": "Pick a file or directory in the tree first.",
    },
    "tui_error_pick_first": {
        "ru": "Сначала выберите файл или директорию.",
        "en": "Pick a file or directory first.",
    },
    "tui_error_verify_needs_baseline": {
        "ru": "Режим verify требует файл baseline.",
        "en": "Verify mode requires a baseline file.",
    },
    "tui_error_verify_conflicts_connect_by": {
        "ru": "Режим verify нельзя сочетать с проверкой CONNECT BY.",
        "en": "Verify mode can't be combined with the CONNECT BY check.",
    },
    "tui_status_scanning": {"ru": "Сканирование...", "en": "Scanning..."},
    "tui_status_verifying": {"ru": "Проверка...", "en": "Verifying..."},
    "tui_error_couldnt_load_baseline": {
        "ru": "Не удалось загрузить baseline: {exc}",
        "en": "Couldn't load baseline: {exc}",
    },
    "tui_warning_not_found": {"ru": "Не найдено: {path}", "en": "Not found: {path}"},
    "tui_warning_could_not_read": {
        "ru": "Не удалось прочитать {path}: {exc}",
        "en": "Could not read {path}: {exc}",
    },
    "tui_warning_no_files_under": {
        "ru": "Файлы .sql/.pks/.pkb не найдены в {dir}",
        "en": "No .sql/.pks/.pkb files found under {dir}",
    },
    "tui_results_select_row_hint": {
        "ru": "Выберите строку, чтобы увидеть полное объяснение.",
        "en": "Select a row to see the full explanation.",
    },
    "tui_save_baseline_input_placeholder": {
        "ru": "Сохранить эти находки как baseline в...",
        "en": "Save these findings as a baseline to...",
    },
    "tui_save_baseline_btn": {"ru": "Сохранить baseline", "en": "Save baseline"},
    "tui_back_to_scan_btn": {"ru": "Назад к сканированию", "en": "Back to scan"},
    "tui_scanned_no_findings": {
        "ru": "Просканировано {path} — проблемных конструкций не найдено.",
        "en": "Scanned {path} — no problematic constructs found.",
    },
    "tui_scanned_summary": {
        "ru": "Просканировано {path} — объектов: {objects}, находок: {count} ({counts_text}) — "
        "грубая оценка {lo:.2f}-{hi:.2f} ч. (неоткалиброванная эвристика, не измерение)",
        "en": "Scanned {path} — objects: {objects}, findings: {count} ({counts_text}) — rough "
        "estimate {lo:.2f}-{hi:.2f}h (uncalibrated heuristic, not a measurement)",
    },
    "tui_error_enter_path_first": {"ru": "Сначала введите путь.", "en": "Enter a path first."},
    "tui_error_couldnt_save": {"ru": "Не удалось сохранить: {exc}", "en": "Couldn't save: {exc}"},
    "tui_saved_findings": {
        "ru": "Сохранено находок: {n} в {path}",
        "en": "Saved {n} findings to {path}",
    },
    "tui_verify_summary": {
        "ru": "Проверено {path} по baseline — детекторов в baseline: {n}: осталось "
        "{still_present}, не обнаружено {not_detected}, нельзя проверить {not_verifiable}",
        "en": "Verified {path} against baseline — {n} baseline detectors: {still_present} "
        "still present, {not_detected} not detected, {not_verifiable} not verifiable",
    },
}


# Detector explanation text (Finding.message), keyed by the exact Russian
# text -- see the module docstring for why. Every detector's message
# constant(s) on disk must have an entry here; scripts/doctor.py enforces
# that (check_explanation_translations_parity()).
EXPLANATION_EN: dict[str, str] = {
    "ora2pg перенесёт эту процедуру/функцию через dblink-обёртку (переименует в *_atx, уберёт "
    "COMMIT из тела, добавит функцию-прокси, вызывающую её через dblink()). Стратегия рабочая, "
    "но не бесшовная: требуется расширение dblink и ручная настройка connection string — то "
    "есть сетевая зависимость между процедурами, которая может быть неприемлема в контуре с "
    "жёсткими требованиями к изоляции. При этом SHOW_REPORT и --estimate_cost систематически "
    "недооценивают стоимость этой конструкции именно для функций/процедур внутри PACKAGE BODY "
    "— сама PRAGMA стоит в декларативной секции (до BEGIN), которая не попадает в подсчёт "
    "стоимости (declare/code split в Ora2Pg.pm::_lookup_function).": (
        "ora2pg will migrate this procedure/function through a dblink wrapper (renaming it to "
        "*_atx, stripping COMMIT from the body, and adding a proxy function that calls it via "
        "dblink()). The strategy works, but isn't seamless: it requires the dblink extension "
        "and manual connection-string setup — i.e. a network dependency between procedures, "
        "which may be unacceptable in an environment with strict isolation requirements. "
        "SHOW_REPORT and --estimate_cost also systematically underestimate the cost of this "
        "construct specifically for functions/procedures inside a PACKAGE BODY — the PRAGMA "
        "itself sits in the declarative section (before BEGIN), which isn't counted toward "
        "cost at all (the declare/code split in Ora2Pg.pm::_lookup_function)."
    ),
    "BULK COLLECT INTO — массовая выборка в коллекцию. ora2pg лишь добавляет ключевое слово "
    "STRICT (относящееся к обычному SELECT INTO в PL/pgSQL, а не к BULK COLLECT) и не "
    "переписывает конструкцию — результат не является корректным PL/pgSQL (подтверждено "
    "реальным прогоном, docs/research/gap-003-bulk-collect-forall.md). Обычно переписывается "
    "на 'SELECT array_agg(...) INTO ...' или цикл с накоплением в массив вручную.": (
        "BULK COLLECT INTO — a bulk fetch into a collection. ora2pg only adds the STRICT "
        "keyword (which applies to a plain SELECT INTO in PL/pgSQL, not to BULK COLLECT) and "
        "doesn't rewrite the construct itself — the result isn't valid PL/pgSQL (confirmed by "
        "a real run, docs/research/gap-003-bulk-collect-forall.md). Usually rewritten as "
        "'SELECT array_agg(...) INTO ...' or a manual loop that accumulates into an array."
    ),
    "FORALL — массовое DML-выполнение по коллекции. В PL/pgSQL такой конструкции нет, ora2pg "
    "копирует её как есть (подтверждено реальным прогоном, "
    "docs/research/gap-003-bulk-collect-forall.md). Обычно переписывается на обычный цикл "
    "FOR ... LOOP или на DML с UNNEST() по массиву — оценка производительности отдельно, "
    "PostgreSQL это тоже умеет делать быстро, просто другим синтаксисом.": (
        "FORALL — bulk DML execution over a collection. PL/pgSQL has no such construct; "
        "ora2pg copies it verbatim (confirmed by a real run, "
        "docs/research/gap-003-bulk-collect-forall.md). Usually rewritten as a plain "
        "FOR ... LOOP or as DML driven by UNNEST() over an array — performance is a separate "
        "question; PostgreSQL can do this fast too, just with different syntax."
    ),
    "TYPE ... IS TABLE OF ... — локальное объявление вложенной коллекции/ассоциативного "
    "массива. ora2pg практически не трогает эту конструкцию — синтаксис копируется как есть, "
    "а такого объявления типа не существует в PL/pgSQL (подтверждено реальным прогоном ora2pg "
    "+ PostgreSQL 16, docs/research/gap-003-bulk-collect-forall.md). CREATE PROCEDURE/FUNCTION "
    "проходит без единой ошибки (ora2pg отключает check_function_bodies в своём выводе), а при "
    "первом же реальном вызове падает прямо на этом объявлении — до того, как тело процедуры "
    "вообще начнёт выполняться. Нужно вручную переписать на массив PostgreSQL (type[]) или "
    "временную таблицу.": (
        "TYPE ... IS TABLE OF ... — a local declaration of a nested collection/associative "
        "array. ora2pg essentially leaves this construct untouched — the syntax is copied "
        "verbatim, and no such type declaration exists in PL/pgSQL (confirmed by a real "
        "ora2pg + PostgreSQL 16 run, docs/research/gap-003-bulk-collect-forall.md). CREATE "
        "PROCEDURE/FUNCTION succeeds without a single error (ora2pg disables "
        "check_function_bodies in its output), and it fails right on this declaration at the "
        "very first real call — before the procedure body even starts executing. Needs to be "
        "manually rewritten as a PostgreSQL array (type[]) or a temporary table."
    ),
    "CREATE TYPE ... AS/IS TABLE OF / VARRAY(n) OF — коллекционный тип Oracle (nested table "
    "или varray), в отличие от объектного типа (см. GAP-009/object_type.py) не помечается "
    "ora2pg как 'Unsupported' и не копируется в вывод вообще — строка полностью пропадает, а в "
    "логе остаётся только служебная строка уровня DEBUG ('unhandled line') (подтверждено "
    "реальным прогоном ora2pg + PostgreSQL 16, docs/research/gap-021-collection-type.md). Это "
    "серьёзнее большинства других gap'ов в этом реестре: любая таблица, использующая такой тип "
    "в качестве типа столбца, падает сразу при загрузке DDL — 'type ... does not exist' — а не "
    "при первом вызове процедуры. У PostgreSQL нет прямого аналога коллекционных типов Oracle "
    "— обычно переписывается на встроенный тип массива (datatype[]) или на отдельную "
    "связанную таблицу.": (
        "CREATE TYPE ... AS/IS TABLE OF / VARRAY(n) OF — an Oracle collection type (nested "
        "table or varray). Unlike an object type (see GAP-009/object_type.py), ora2pg doesn't "
        "mark it 'Unsupported' — it isn't copied into the output at all: the line simply "
        "disappears, leaving only a DEBUG-level log line ('unhandled line') (confirmed by a "
        "real ora2pg + PostgreSQL 16 run, docs/research/gap-021-collection-type.md). This is "
        "more severe than most other gaps in this registry: any table that uses this type as "
        "a column type fails immediately on DDL load — 'type ... does not exist' — not on the "
        "procedure's first call. PostgreSQL has no direct equivalent of Oracle's collection "
        "types — usually rewritten as a built-in array type (datatype[]) or a separate linked "
        "table."
    ),
    "COMPOUND TRIGGER: секции BEFORE STATEMENT / BEFORE EACH ROW / AFTER EACH ROW / AFTER "
    "STATEMENT внутри одного триггера. У ora2pg нет отдельного пути конвертации для этого "
    "синтаксиса. В файловом режиме (-t TRIGGER -i file.sql) его regex-парсер "
    "(read_trigger_from_file) рассчитан на классическую форму 'ON <table> [FOR EACH ROW] "
    "[WHEN (...)] BEGIN...END' и на составном триггере тихо возвращает 0 найденных триггеров "
    "— без единой ошибки или предупреждения (эмпирически подтверждено, "
    "docs/research/step0-show-report-baseline.md, раздел 5). В режиме живого подключения "
    "счётчик объектов SHOW_REPORT покажет этот триггер как обычный валидный (данные берутся "
    "из каталога Oracle, а не из попытки конвертации) — то есть само число объектов проблему "
    "не выдаст. По структуре export_trigger() в Ora2Pg.pm крайне вероятно, что и в живом "
    "режиме конвертация тела COMPOUND TRIGGER даёт синтаксически неверный или тихо испорченный "
    "код. Нужен ручной перенос — как правило, на несколько независимых обычных триггеров "
    "(BEFORE/AFTER × STATEMENT/ROW) с общим состоянием через пакетную переменную или временную "
    "таблицу вместо секций компаунд-триггера.": (
        "COMPOUND TRIGGER: BEFORE STATEMENT / BEFORE EACH ROW / AFTER EACH ROW / AFTER "
        "STATEMENT sections inside a single trigger. ora2pg has no dedicated conversion path "
        "for this syntax. In file mode (-t TRIGGER -i file.sql), its regex parser "
        "(read_trigger_from_file) is built for the classic form 'ON <table> [FOR EACH ROW] "
        "[WHEN (...)] BEGIN...END', and on a compound trigger it silently returns 0 triggers "
        "found — no error, no warning (confirmed empirically, "
        "docs/research/step0-show-report-baseline.md, section 5). In live-connection mode, "
        "SHOW_REPORT's object count will list this trigger as an ordinary, valid one (the "
        "data comes from the Oracle catalog, not from an actual conversion attempt) — so the "
        "object count alone won't reveal the problem. Based on how export_trigger() is "
        "structured in Ora2Pg.pm, it's highly likely that live-mode conversion of a COMPOUND "
        "TRIGGER body also produces syntactically invalid or silently broken code. Needs a "
        "manual migration — typically to several independent ordinary triggers "
        "(BEFORE/AFTER × STATEMENT/ROW) sharing state through a package variable or a "
        "temporary table instead of compound-trigger sections."
    ),
    "Сгенерированный ora2pg WITH RECURSIVE ссылается на LEVEL — псевдоколонку Oracle, которой "
    "нет ни в PostgreSQL, ни в самом CTE. ora2pg переименовывает LEVEL в столбец-счётчик "
    "глубины в анкорной ветке CTE, но не везде — известный баг подстановки его regex-based "
    "конвертера CONNECT BY (docs/research/step0-show-report-baseline.md, раздел 3; "
    "воспроизведено на реальном прогоне ora2pg). Сгенерированный SQL в этом виде не выполнится "
    "в PostgreSQL без ручной правки — LEVEL нужно заменить на настоящее имя колонки-счётчика. "
    "Строка в этой находке относится к сгенерированному ora2pg коду, а не к исходному "
    "Oracle-файлу — используйте имя объекта и фрагмент ниже, чтобы найти проблему, а не номер "
    "строки.": (
        "The WITH RECURSIVE that ora2pg generates references LEVEL — an Oracle pseudocolumn "
        "that exists neither in PostgreSQL nor in the CTE itself. ora2pg renames LEVEL to a "
        "depth-counter column in the CTE's anchor branch, but not everywhere — a known "
        "substitution bug in its regex-based CONNECT BY converter "
        "(docs/research/step0-show-report-baseline.md, section 3; reproduced on a real ora2pg "
        "run). The generated SQL as it stands won't run in PostgreSQL without a manual fix — "
        "LEVEL needs to be replaced with the actual counter column's name. The line number in "
        "this finding refers to ora2pg's *generated* code, not the original Oracle file — use "
        "the object name and snippet below to locate the problem, not the line number."
    ),
    "CONNECT BY NOCYCLE / ORDER SIBLINGS BY — расширения иерархических запросов Oracle сверх "
    "базового CONNECT BY. В отличие от обычного CONNECT BY (см. GAP-005/detectors/connect_by.py, "
    "где конвертация работает с известным багом LEVEL), эти конструкции ломают конвертацию "
    "гораздо серьёзнее: ora2pg не просто переносит их неточно, а разваливает структуру всего "
    "PL/SQL-блока — сгенерированный WITH RECURSIVE оказывается вставлен ДО DECLARE, а тело "
    "процедуры получает нарушенную вложенность DECLARE/CURSOR (подтверждено реальным прогоном "
    "ora2pg + PostgreSQL 16, docs/research/gap-014-connect-by-nocycle.md). Падает уже на этапе "
    "компиляции тела функции при первом вызове, не просто на выполнении. Нужен полностью "
    "ручной переход на WITH RECURSIVE.": (
        "CONNECT BY NOCYCLE / ORDER SIBLINGS BY — extensions to Oracle's hierarchical queries "
        "beyond plain CONNECT BY. Unlike plain CONNECT BY (see GAP-005/detectors/connect_by.py, "
        "where conversion works but has a known LEVEL bug), these constructs break conversion "
        "far more severely: ora2pg doesn't just translate them inaccurately, it breaks the "
        "structure of the whole PL/SQL block — the generated WITH RECURSIVE ends up inserted "
        "BEFORE DECLARE, and the procedure body gets a broken DECLARE/CURSOR nesting "
        "(confirmed by a real ora2pg + PostgreSQL 16 run, "
        "docs/research/gap-014-connect-by-nocycle.md). It fails at the function body's "
        "compilation stage on the first call, not just at execution. Requires a fully manual "
        "rewrite to WITH RECURSIVE."
    ),
    "CREATE CONTEXT — объявление application context (часто основа VPD/row-level security "
    "через SYS_CONTEXT в связке с DBMS_SESSION.SET_CONTEXT). ora2pg не конвертирует эту "
    "конструкцию вообще — она полностью пропадает из вывода, без сгенерированного "
    "PostgreSQL-эквивалента (подтверждено реальным прогоном ora2pg, "
    "docs/research/gap-015-context.md). В логах есть только служебная строка уровня DEBUG "
    "('unhandled line'), а не предупреждение — легко пропустить при реальной миграции. У "
    "PostgreSQL нет прямого аналога application context — обычно переписывается на "
    "current_setting()/set_config() с ручным управлением видимостью, или на Row-Level Security "
    "(CREATE POLICY) для сценария VPD.": (
        "CREATE CONTEXT — an application context declaration (often the basis for VPD/"
        "row-level security via SYS_CONTEXT combined with DBMS_SESSION.SET_CONTEXT). ora2pg "
        "doesn't convert this construct at all — it disappears from the output entirely, with "
        "no generated PostgreSQL equivalent (confirmed by a real ora2pg run, "
        "docs/research/gap-015-context.md). The logs contain only a DEBUG-level line "
        "('unhandled line'), not a warning — easy to miss during a real migration. PostgreSQL "
        "has no direct equivalent of an application context — usually rewritten using "
        "current_setting()/set_config() with manual visibility management, or Row-Level "
        "Security (CREATE POLICY) for a VPD-style scenario."
    ),
    "CROSS APPLY / OUTER APPLY (Oracle 12c+) — вызов табличного подзапроса для каждой строки "
    "внешнего запроса с возможностью ссылаться на её столбцы, аналог LATERAL JOIN. ora2pg "
    "копирует конструкцию как есть, без изменений (подтверждено реальным прогоном ora2pg + "
    "PostgreSQL 16, docs/research/gap-022-cross-apply.md). PostgreSQL не имеет синтаксиса "
    "APPLY вообще — падает с синтаксической ошибкой уже на этапе компиляции тела функции при "
    "первом вызове. Нужно вручную переписать на 'JOIN LATERAL (...) ON true' (CROSS APPLY) "
    "или 'LEFT JOIN LATERAL (...) ON true' (OUTER APPLY).": (
        "CROSS APPLY / OUTER APPLY (Oracle 12c+) — invokes a table subquery once per row of "
        "the outer query, with the ability to reference that row's columns; equivalent to a "
        "LATERAL JOIN. ora2pg copies the construct verbatim, unchanged (confirmed by a real "
        "ora2pg + PostgreSQL 16 run, docs/research/gap-022-cross-apply.md). PostgreSQL has no "
        "APPLY syntax at all — it fails with a syntax error at the function body's compilation "
        "stage on the first call. Needs to be manually rewritten as 'JOIN LATERAL (...) ON "
        "true' (for CROSS APPLY) or 'LEFT JOIN LATERAL (...) ON true' (for OUTER APPLY)."
    ),
    "table@dblink_name — прямая ссылка на объект в удалённой базе через database link. ora2pg "
    "копирует ссылку как есть — '@dblink_name' не валидный синтаксис SQL в PostgreSQL вообще "
    "(подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-006-database-link.md). CREATE PROCEDURE/FUNCTION проходит без ошибки "
    "(ora2pg отключает check_function_bodies в своём выводе), падает только при первом "
    "реальном вызове. Автоматической замены нет и в принципе быть не может — нужна ручная "
    "настройка postgres_fdw/dblink с реальными connection-параметрами удалённой базы.": (
        "table@dblink_name — a direct reference to an object in a remote database via a "
        "database link. ora2pg copies the reference verbatim — '@dblink_name' isn't valid SQL "
        "syntax in PostgreSQL at all (confirmed by a real ora2pg + PostgreSQL 16 run, "
        "docs/research/gap-006-database-link.md). CREATE PROCEDURE/FUNCTION succeeds without "
        "error (ora2pg disables check_function_bodies in its output), and it only fails on "
        "the first real call. There's no automatic replacement, and there fundamentally can't "
        "be one — it needs manual postgres_fdw/dblink setup with the remote database's real "
        "connection parameters."
    ),
    "Специальной конвертации в ora2pg для этого конкретного вызова не найдено (проверено по "
    "исходникам Ora2Pg/PLSQL.pm на шаге 0) — он попадёт только в обезличенный счётчик "
    "DBMS_/UTL_ (вес 3 в estimate_cost), а сам код останется как есть и не скомпилируется в "
    "PostgreSQL без ручного переписывания или подключения расширения orafce (если для этой "
    "функции там вообще есть эквивалент).": (
        "No dedicated conversion for this specific call was found in ora2pg (checked against "
        "Ora2Pg/PLSQL.pm's own source at step 0) — it only feeds into the generic DBMS_/UTL_ "
        "counter (weight 3 in estimate_cost), while the code itself is left as-is and won't "
        "compile in PostgreSQL without manual rewriting or the orafce extension (if it "
        "happens to have an equivalent for this function at all)."
    ),
    "CREATE TABLE ... ORGANIZATION EXTERNAL — внешняя таблица Oracle, читающая данные "
    "напрямую из файла (ORACLE_LOADER/ORACLE_DATAPUMP), а не хранящая их в самой БД. ora2pg "
    "отбрасывает всю секцию ORGANIZATION EXTERNAL целиком, включая TYPE/DEFAULT "
    "DIRECTORY/ACCESS PARAMETERS/LOCATION — таблица создаётся как обычная, физически "
    "хранимая, без единого предупреждения и без сигнала в --estimate_cost (подтверждено "
    "реальным прогоном ora2pg + PostgreSQL 16, docs/research/gap-018-external-table.md). Это "
    "не синтаксическая ошибка — CREATE TABLE выполняется без проблем, но результат совсем "
    "другой: источник данных (файл) исчезает бесследно, таблица остаётся пустой и никогда не "
    "подхватит содержимое файла. Ближайший эквивалент в PostgreSQL — foreign table через "
    "file_fdw (или конкретный fdw для нужного формата) — настраивается вручную.": (
        "CREATE TABLE ... ORGANIZATION EXTERNAL — an Oracle external table that reads data "
        "directly from a file (ORACLE_LOADER/ORACLE_DATAPUMP) rather than storing it in the "
        "database itself. ora2pg drops the entire ORGANIZATION EXTERNAL section, including "
        "TYPE/DEFAULT DIRECTORY/ACCESS PARAMETERS/LOCATION — the table is created as an "
        "ordinary, physically-stored one, with no warning and no signal in --estimate_cost "
        "(confirmed by a real ora2pg + PostgreSQL 16 run, "
        "docs/research/gap-018-external-table.md). This isn't a syntax error — CREATE TABLE "
        "runs without a problem, but the result is something entirely different: the data "
        "source (the file) vanishes without a trace, the table stays empty and will never "
        "pick up the file's contents. The closest PostgreSQL equivalent is a foreign table "
        "via file_fdw (or a specific fdw for the format needed) — set up manually."
    ),
    "AS OF TIMESTAMP/SCN — flashback-запрос, читающий таблицу такой, какой она была в "
    "прошлом. ora2pg копирует конструкцию как есть (с побочным искажением текста при "
    "подстановке SYSTIMESTAMP в некоторых случаях — подтверждено реальным прогоном, "
    "docs/research/gap-011-flashback-query.md) — в PostgreSQL нет встроенного эквивалента "
    "вообще. CREATE PROCEDURE/FUNCTION проходит без ошибки, падает только при первом реальном "
    "вызове. Нужен отдельный архитектурный механизм (temporal tables через расширение, "
    "собственные таблицы истории/аудита) — не синтаксическая замена.": (
        "AS OF TIMESTAMP/SCN — a flashback query that reads a table as it looked in the past. "
        "ora2pg copies the construct verbatim (with an incidental text mangling when "
        "substituting SYSTIMESTAMP in some cases — confirmed by a real run, "
        "docs/research/gap-011-flashback-query.md) — PostgreSQL has no built-in equivalent at "
        "all. CREATE PROCEDURE/FUNCTION succeeds without error, and it only fails on the "
        "first real call. Needs a separate architectural mechanism (temporal tables via an "
        "extension, custom history/audit tables) — not a syntax substitution."
    ),
    "CREATE GLOBAL TEMPORARY TABLE без ON COMMIT PRESERVE ROWS — то есть либо явный ON COMMIT "
    "DELETE ROWS, либо секция ON COMMIT вообще опущена (по умолчанию в Oracle это тоже DELETE "
    "ROWS). ora2pg конвертирует в CREATE TEMPORARY TABLE, но полностью теряет секцию ON "
    "COMMIT — не подставляет её PostgreSQL-эквивалент (подтверждено реальным прогоном ora2pg "
    "+ PostgreSQL 16, docs/research/gap-012-global-temp-table.md). У обычной CREATE TEMPORARY "
    "TABLE в PostgreSQL поведение по умолчанию — как раз PRESERVE ROWS, противоположное "
    "Oracle-семантике DELETE ROWS. Это не синтаксическая ошибка — код молча компилируется и "
    "выполняется, но строки, которые в Oracle должны были очищаться после каждого COMMIT, в "
    "PostgreSQL остаются до конца сессии. Нужно вручную добавить 'ON COMMIT DELETE ROWS' в "
    "определение таблицы.": (
        "CREATE GLOBAL TEMPORARY TABLE without ON COMMIT PRESERVE ROWS — meaning either an "
        "explicit ON COMMIT DELETE ROWS, or the ON COMMIT section omitted entirely (Oracle's "
        "default is also DELETE ROWS). ora2pg converts it to CREATE TEMPORARY TABLE but drops "
        "the ON COMMIT section completely — it never substitutes PostgreSQL's equivalent "
        "(confirmed by a real ora2pg + PostgreSQL 16 run, "
        "docs/research/gap-012-global-temp-table.md). An ordinary CREATE TEMPORARY TABLE in "
        "PostgreSQL defaults to exactly PRESERVE ROWS — the opposite of Oracle's DELETE ROWS "
        "semantics. This isn't a syntax error — the code silently compiles and runs, but rows "
        "that in Oracle should have been cleared after every COMMIT now stay until the end of "
        "the session in PostgreSQL. Needs 'ON COMMIT DELETE ROWS' added to the table "
        "definition by hand."
    ),
    "GENERATED ALWAYS/BY DEFAULT AS IDENTITY (...) с явными опциями последовательности (START "
    "WITH/INCREMENT BY/MAXVALUE и т.д.) — ora2pg переносит их в PostgreSQL-эквивалент, но "
    "оборачивает секцию опций в лишнюю пару скобок: 'GENERATED ALWAYS AS IDENTITY ((START "
    "WITH 1 INCREMENT BY 1))' вместо корректного 'GENERATED ALWAYS AS IDENTITY (START WITH 1 "
    "INCREMENT BY 1)' (подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-028-identity-column.md). Это не пропуск конвертации, а именно баг "
    "самой подстановки — сам CREATE TABLE падает немедленно при загрузке DDL, ещё до вызова "
    "любой функции: 'ERROR: syntax error at or near \"(\"'. Отдельно проверено: GENERATED "
    "ALWAYS AS IDENTITY без явных опций (пустые скобки не нужны) конвертируется корректно — "
    "баг специфичен именно для случая с опциями. Нужно вручную убрать лишнюю внешнюю пару "
    "скобок.": (
        "GENERATED ALWAYS/BY DEFAULT AS IDENTITY (...) with explicit sequence options (START "
        "WITH/INCREMENT BY/MAXVALUE etc.) — ora2pg carries these over to the PostgreSQL "
        "equivalent, but wraps the options section in an extra, unwanted pair of parentheses: "
        "'GENERATED ALWAYS AS IDENTITY ((START WITH 1 INCREMENT BY 1))' instead of the "
        "correct 'GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1)' (confirmed by a "
        "real ora2pg + PostgreSQL 16 run, docs/research/gap-028-identity-column.md). This "
        "isn't a skipped conversion, it's a genuine substitution bug — CREATE TABLE itself "
        "fails immediately on DDL load, before any function is even called: 'ERROR: syntax "
        "error at or near \"(\"'. Separately verified: GENERATED ALWAYS AS IDENTITY without "
        "explicit options (no parentheses needed) converts correctly — the bug is specific to "
        "the case with options. Needs the extra outer pair of parentheses removed by hand."
    ),
    "INSERT ALL / INSERT FIRST — многотабличная вставка Oracle (условная или безусловная, "
    "WHEN ... THEN INTO ... либо просто несколько INTO подряд). PostgreSQL не имеет такого "
    "синтаксиса вообще — ora2pg копирует конструкцию как есть, без единого предупреждения "
    "(подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-016-insert-all.md). Это не просто неточный перевод — PL/pgSQL "
    "пытается разобрать 'INTO таблица' как INTO для переменной (как в SELECT ... INTO), а не "
    "как ветку многотабличной вставки, и падает уже на этапе компиляции тела функции. Нужно "
    "вручную переписать на набор отдельных INSERT INTO ... SELECT ..., по одному на каждую "
    "ветку.": (
        "INSERT ALL / INSERT FIRST — Oracle's multi-table insert (conditional or "
        "unconditional, WHEN ... THEN INTO ... or just several INTO clauses in a row). "
        "PostgreSQL has no such syntax at all — ora2pg copies the construct verbatim, with no "
        "warning (confirmed by a real ora2pg + PostgreSQL 16 run, "
        "docs/research/gap-016-insert-all.md). This isn't just an inaccurate translation — "
        "PL/pgSQL tries to parse 'INTO table' as an INTO for a variable (as in SELECT ... "
        "INTO), not as a multi-table-insert branch, and fails at the function body's "
        "compilation stage. Needs to be manually rewritten as a set of separate INSERT INTO "
        "... SELECT ... statements, one per branch."
    ),
    "Столбец INVISIBLE — Oracle исключает такой столбец из SELECT * и из позиционного INSERT "
    "без явного списка столбцов, показывая его только при явном упоминании по имени. ora2pg "
    "отбрасывает модификатор INVISIBLE целиком — столбец конвертируется как обычный, видимый "
    "(подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-020-invisible-column.md; в самом PostgreSQL нет аналога INVISIBLE "
    "вообще). Это не ошибка — CREATE TABLE выполняется без проблем, но поведение меняется "
    "тихо: SELECT * начинает возвращать столбец, который в Oracle был из него исключён. Для "
    "столбцов, специально скрытых от старого клиентского кода при добавлении новой колонки "
    "(типичный сценарий использования INVISIBLE), это может неожиданно сломать код, "
    "полагавшийся на прежний набор столбцов в SELECT *.": (
        "An INVISIBLE column — Oracle excludes such a column from SELECT * and from a "
        "positional INSERT with no explicit column list, showing it only when referenced by "
        "name explicitly. ora2pg drops the INVISIBLE modifier entirely — the column converts "
        "as an ordinary, visible one (confirmed by a real ora2pg + PostgreSQL 16 run, "
        "docs/research/gap-020-invisible-column.md; PostgreSQL itself has no INVISIBLE "
        "equivalent at all). This isn't an error — CREATE TABLE runs without a problem, but "
        "the behavior changes silently: SELECT * starts returning a column that Oracle "
        "excluded from it. For columns deliberately hidden from old client code when adding a "
        "new column (a typical use case for INVISIBLE), this can unexpectedly break code that "
        "relied on the previous SELECT * column set."
    ),
    "Индекс INVISIBLE — Oracle не использует такой индекс в планах выполнения по умолчанию "
    "(пока сессия явно не включит OPTIMIZER_USE_INVISIBLE_INDEXES), но продолжает его "
    "поддерживать при DML — типичный сценарий: добавить индекс невидимым, проверить нагрузку, "
    "потом сделать VISIBLE. ora2pg отбрасывает модификатор INVISIBLE целиком — индекс "
    "конвертируется как обычный, видимый (подтверждено реальным прогоном ora2pg + PostgreSQL "
    "16, docs/research/gap-025-invisible-index.md; в самом PostgreSQL нет аналога INVISIBLE "
    "для индексов вообще). Не ошибка — CREATE INDEX выполняется без проблем, но поведение "
    "меняется тихо: оптимизатор PostgreSQL сразу начинает учитывать индекс, которого в "
    "Oracle-плане по умолчанию не было бы — потенциально другой план выполнения там, где это "
    "не ожидалось.": (
        "An INVISIBLE index — Oracle doesn't use such an index in execution plans by default "
        "(unless a session explicitly enables OPTIMIZER_USE_INVISIBLE_INDEXES), but still "
        "maintains it on DML — a typical use case is adding an index invisibly, checking the "
        "load impact, then making it VISIBLE. ora2pg drops the INVISIBLE modifier entirely — "
        "the index converts as an ordinary, visible one (confirmed by a real ora2pg + "
        "PostgreSQL 16 run, docs/research/gap-025-invisible-index.md; PostgreSQL itself has "
        "no INVISIBLE equivalent for indexes at all). Not an error — CREATE INDEX runs "
        "without a problem, but the behavior changes silently: PostgreSQL's optimizer "
        "immediately starts factoring in an index that wouldn't have been in Oracle's default "
        "plan — potentially a different execution plan where none was expected."
    ),
    "JSON_TABLE(...) — табличная проекция JSON-документа в реляционные строки/столбцы. "
    "ora2pg копирует вызов как есть (подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-017-json-table.md). На PostgreSQL 16 и старше падает с синтаксической "
    "ошибкой прямо на COLUMNS — функции JSON_TABLE в PostgreSQL нет вообще (появилась только "
    "в PostgreSQL 17, и то с другим синтаксисом секции COLUMNS, не идентичным Oracle — не "
    "проверялось эмпирически в этом исследовании, но использовать как прямую замену без "
    "сверки нельзя). До PostgreSQL 17 нужен полностью ручной переход на "
    "jsonb_to_recordset()/jsonb_array_elements() с явным приведением типов.": (
        "JSON_TABLE(...) — projects a JSON document into relational rows/columns. ora2pg "
        "copies the call verbatim (confirmed by a real ora2pg + PostgreSQL 16 run, "
        "docs/research/gap-017-json-table.md). On PostgreSQL 16 and earlier it fails with a "
        "syntax error right at COLUMNS — PostgreSQL has no JSON_TABLE function at all (it "
        "only appeared in PostgreSQL 17, and even then with a different COLUMNS-section "
        "syntax that isn't identical to Oracle's — not verified empirically in this research, "
        "but it can't be used as a drop-in replacement without checking). Before PostgreSQL "
        "17, needs a fully manual rewrite to jsonb_to_recordset()/jsonb_array_elements() with "
        "explicit type casts."
    ),
    "CREATE MATERIALIZED VIEW LOG ON ... — журнал изменений таблицы, нужный для FAST REFRESH "
    "материализованных представлений, построенных на ней. ora2pg не конвертирует эту "
    "конструкцию вообще — она полностью пропадает из вывода, без единого предупреждения "
    "(подтверждено реальным прогоном ora2pg, docs/research/gap-027-materialized-view-log.md). "
    "В логе есть только служебная строка уровня DEBUG ('unhandled line'), не предупреждение "
    "— легко пропустить при реальной миграции. Если на этой таблице где-то построено "
    "материализованное представление с REFRESH FAST, оно перестанет работать в режиме "
    "быстрого обновления (FAST), поскольку в PostgreSQL у материализованных представлений "
    "нет инкрементального REFRESH FAST вообще — только полный REFRESH (`REFRESH MATERIALIZED "
    "VIEW`), что делает саму журнальную таблицу ненужной, но означает архитектурно другой "
    "подход к обновлению данных.": (
        "CREATE MATERIALIZED VIEW LOG ON ... — a change log for a table, needed for FAST "
        "REFRESH of materialized views built on it. ora2pg doesn't convert this construct at "
        "all — it disappears from the output entirely, with no warning (confirmed by a real "
        "ora2pg run, docs/research/gap-027-materialized-view-log.md). The log contains only a "
        "DEBUG-level line ('unhandled line'), not a warning — easy to miss during a real "
        "migration. If a materialized view with REFRESH FAST is built anywhere on this table, "
        "it will stop working in fast-refresh (FAST) mode, because PostgreSQL's materialized "
        "views have no incremental REFRESH FAST at all — only a full REFRESH (`REFRESH "
        "MATERIALIZED VIEW`), which makes the log table itself unnecessary but means an "
        "architecturally different approach to keeping data up to date."
    ),
    "MERGE ... WHEN MATCHED THEN UPDATE SET ... DELETE WHERE ... — составная "
    "Oracle-конструкция, удаляющая часть только что обновлённых строк. ora2pg копирует её как "
    "есть (подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-002-merge-delete-clause.md), а в MERGE PostgreSQL (15+) такого нет — "
    "каждая ветка WHEN является одним действием (UPDATE/DELETE/INSERT/DO NOTHING), а не "
    "составным UPDATE-затем-DELETE. Подтверждено на реальном PostgreSQL 16: CREATE PROCEDURE "
    "проходит без единой ошибки (ora2pg отключает check_function_bodies в своём выводе), "
    "синтаксическая ошибка всплывает только при первом реальном вызове — то есть в проде, а "
    "не на этапе компиляции. Обычный MERGE (UPDATE+INSERT, без DELETE WHERE) — не проблема, "
    "конвертируется и выполняется корректно. Нужно вручную разбить на две ветки WHEN MATCHED "
    "со взаимоисключающими условиями вместо составной конструкции.": (
        "MERGE ... WHEN MATCHED THEN UPDATE SET ... DELETE WHERE ... — a compound Oracle "
        "construct that deletes a subset of the rows it just updated. ora2pg copies it "
        "verbatim (confirmed by a real ora2pg + PostgreSQL 16 run, "
        "docs/research/gap-002-merge-delete-clause.md), but PostgreSQL's MERGE (15+) has "
        "nothing like it — each WHEN branch is a single action (UPDATE/DELETE/INSERT/DO "
        "NOTHING), not a compound UPDATE-then-DELETE. Confirmed on real PostgreSQL 16: CREATE "
        "PROCEDURE succeeds without a single error (ora2pg disables check_function_bodies in "
        "its output), and the syntax error only surfaces on the first real call — i.e. in "
        "production, not at compile time. A plain MERGE (UPDATE+INSERT, no DELETE WHERE) "
        "isn't a problem — it converts and runs correctly. Needs to be manually split into "
        "two WHEN MATCHED branches with mutually exclusive conditions instead of the compound "
        "construct."
    ),
    "MODEL — spreadsheet-стиль вычислений внутри SQL (PARTITION BY / DIMENSION BY / MEASURES "
    "/ RULES). ora2pg не трогает конструкцию вообще (подтверждено реальным прогоном ora2pg + "
    "PostgreSQL 16, docs/research/gap-007-model-clause.md). CREATE PROCEDURE/FUNCTION "
    "проходит без ошибки (ora2pg отключает check_function_bodies в своём выводе), падает "
    "только при первом реальном вызове. В отличие от большинства других находок этого "
    "проекта, у MODEL нет прямого архитектурного эквивалента в PostgreSQL вообще — "
    "единственный путь это переписать логику вручную на оконные функции или рекурсивные CTE, "
    "а не механическая подстановка синтаксиса.": (
        "MODEL — spreadsheet-style computation inside SQL (PARTITION BY / DIMENSION BY / "
        "MEASURES / RULES). ora2pg leaves the construct completely untouched (confirmed by a "
        "real ora2pg + PostgreSQL 16 run, docs/research/gap-007-model-clause.md). CREATE "
        "PROCEDURE/FUNCTION succeeds without error (ora2pg disables check_function_bodies in "
        "its output), and it only fails on the first real call. Unlike most other findings in "
        "this project, MODEL has no direct architectural equivalent in PostgreSQL at all — "
        "the only path is to manually rewrite the logic using window functions or recursive "
        "CTEs, not a mechanical syntax substitution."
    ),
    "CREATE TYPE ... AS OBJECT / TYPE BODY — объектный тип Oracle (атрибуты + MEMBER-методы). "
    "ora2pg сам явно помечает это '-- Unsupported, please edit to match PostgreSQL syntax' и "
    "копирует Oracle-синтаксис как есть — но что важнее, у --estimate_cost (и, судя по коду, "
    "у SHOW_REPORT) вообще нет механизма оценки стоимости для объектов типа TYPE "
    "(подтверждено прогоном --estimate_cost -t TYPE, вернувшим ноль строк отчёта, см. "
    "docs/research/gap-009-object-type.md). Значит такие объекты не просто помечены как "
    "проблема — они полностью выпадают из любой числовой оценки трудозатрат. У PostgreSQL нет "
    "объектных типов с методами — обычно переписывается на composite type + отдельные "
    "функции, архитектурно другой подход, не механическая замена синтаксиса.": (
        "CREATE TYPE ... AS OBJECT / TYPE BODY — an Oracle object type (attributes plus "
        "MEMBER methods). ora2pg explicitly marks it '-- Unsupported, please edit to match "
        "PostgreSQL syntax' and copies the Oracle syntax verbatim — but more importantly, "
        "--estimate_cost (and, judging by the code, SHOW_REPORT too) has no cost-estimation "
        "mechanism for TYPE objects at all (confirmed by running --estimate_cost -t TYPE, "
        "which returned zero report rows, see docs/research/gap-009-object-type.md). So these "
        "objects aren't just flagged as a problem — they fall out of any numeric effort "
        "estimate entirely. PostgreSQL has no object types with methods — usually rewritten "
        "as a composite type plus separate functions, an architecturally different approach, "
        "not a mechanical syntax swap."
    ),
    "Oracle Text — полнотекстовый поиск через домен-индекс (CREATE INDEX ... INDEXTYPE IS "
    "CTXSYS.CONTEXT/CTXCAT/CTXRULE) и функции CONTAINS()/CATSEARCH()/MATCHES(). ora2pg "
    "отбрасывает секцию INDEXTYPE целиком — индекс создаётся как обычный B-tree по столбцу, "
    "без единого предупреждения; вызовы CONTAINS()/CATSEARCH()/MATCHES() копируются как есть "
    "(подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-023-oracle-text.md). Обычный B-tree индекс не даёт полнотекстового "
    "поиска вообще — не синтаксическая ошибка, а тихая потеря всей функциональности; вызовы "
    "CONTAINS()/CATSEARCH()/MATCHES() падают при первом вызове: 'function contains(text, "
    "unknown) does not exist'. У PostgreSQL есть архитектурный эквивалент — полнотекстовый "
    "поиск через tsvector/tsquery и GIN-индекс (`to_tsvector`/`@@`), но это требует ручного "
    "переписывания, не механической замены синтаксиса.": (
        "Oracle Text — full-text search via a domain index (CREATE INDEX ... INDEXTYPE IS "
        "CTXSYS.CONTEXT/CTXCAT/CTXRULE) and the CONTAINS()/CATSEARCH()/MATCHES() functions. "
        "ora2pg drops the INDEXTYPE section entirely — the index is created as an ordinary "
        "B-tree on the column, with no warning; calls to CONTAINS()/CATSEARCH()/MATCHES() are "
        "copied verbatim (confirmed by a real ora2pg + PostgreSQL 16 run, "
        "docs/research/gap-023-oracle-text.md). An ordinary B-tree index provides no "
        "full-text search at all — not a syntax error, but a silent loss of the entire "
        "feature; calls to CONTAINS()/CATSEARCH()/MATCHES() fail on the first call: 'function "
        "contains(text, unknown) does not exist'. PostgreSQL has an architectural equivalent "
        "— full-text search via tsvector/tsquery and a GIN index (`to_tsvector`/`@@`), but it "
        "requires manual rewriting, not a mechanical syntax swap."
    ),
    "PIVOT/UNPIVOT — поворот строк в столбцы (и обратно) прямо в SQL. ora2pg копирует "
    "конструкцию как есть (подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-008-pivot-unpivot.md) — в PostgreSQL нет встроенного PIVOT/UNPIVOT "
    "вообще. CREATE PROCEDURE/FUNCTION проходит без ошибки (ora2pg отключает "
    "check_function_bodies в своём выводе), падает только при первом реальном вызове. "
    "Переписывается вручную на условную агрегацию (FILTER/CASE WHEN) или расширение "
    "tablefunc (crosstab()).": (
        "PIVOT/UNPIVOT — turns rows into columns (and back) directly in SQL. ora2pg copies "
        "the construct verbatim (confirmed by a real ora2pg + PostgreSQL 16 run, "
        "docs/research/gap-008-pivot-unpivot.md) — PostgreSQL has no built-in PIVOT/UNPIVOT "
        "at all. CREATE PROCEDURE/FUNCTION succeeds without error (ora2pg disables "
        "check_function_bodies in its output), and it only fails on the first real call. "
        "Rewritten manually as conditional aggregation (FILTER/CASE WHEN) or the tablefunc "
        "extension (crosstab())."
    ),
    "CREATE TABLE ... READ ONLY — Oracle блокирует любой INSERT/UPDATE/DELETE в такую "
    "таблицу на уровне сервера (ORA-12081), независимо от привилегий пользователя. ora2pg "
    "отбрасывает секцию READ ONLY целиком — таблица конвертируется как обычная, доступная "
    "для записи (подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-026-read-only-table.md; проверено напрямую — INSERT в сконвертированную "
    "таблицу проходит успешно там, где в Oracle он был бы гарантированно заблокирован). Не "
    "синтаксическая ошибка — CREATE TABLE выполняется без проблем, но потеряна гарантия "
    "целостности данных на уровне БД, которая могла быть единственной защитой (например, для "
    "таблицы-снапшота или исторического архива). В PostgreSQL прямого аналога нет — обычно "
    "переписывается через REVOKE INSERT/UPDATE/DELETE от всех ролей (включая владельца) или "
    "через BEFORE-триггер, отклоняющий DML.": (
        "CREATE TABLE ... READ ONLY — Oracle blocks any INSERT/UPDATE/DELETE against such a "
        "table at the server level (ORA-12081), regardless of the user's privileges. ora2pg "
        "drops the READ ONLY section entirely — the table converts as an ordinary, writable "
        "one (confirmed by a real ora2pg + PostgreSQL 16 run, "
        "docs/research/gap-026-read-only-table.md; verified directly — an INSERT into the "
        "converted table succeeds where it would have been reliably blocked in Oracle). Not a "
        "syntax error — CREATE TABLE runs without a problem, but a database-level "
        "data-integrity guarantee is lost, one that may have been the table's only protection "
        "(e.g. for a snapshot table or a historical archive). PostgreSQL has no direct "
        "equivalent — usually rewritten via REVOKE INSERT/UPDATE/DELETE from all roles "
        "(including the owner) or a BEFORE trigger that rejects DML."
    ),
    "WITH cte AS (...) — рекурсивная факторизация подзапроса Oracle (recursive subquery "
    "factoring), не через CONNECT BY (см. GAP-005 про этот отдельный случай), а через прямую "
    "самоссылку CTE на себя после UNION [ALL]. Oracle не требует явного ключевого слова "
    "RECURSIVE — рекурсия определяется автоматически по самоссылке. ora2pg копирует WITH как "
    "есть, без добавления RECURSIVE (подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-024-recursive-with.md). PostgreSQL требует RECURSIVE явно — без него "
    "самоссылка на CTE во второй ветке UNION падает: 'there is a WITH item named ..., but it "
    "cannot be referenced from this part of the query' с подсказкой 'Use WITH RECURSIVE'. "
    "Если запрос дополнительно использует секцию CYCLE, после добавления RECURSIVE вручную "
    "придётся ещё и переставить её после закрывающей скобки тела CTE и добавить обязательную "
    "в PostgreSQL секцию USING — у Oracle CYCLE стоит перед AS и не требует USING.": (
        "WITH cte AS (...) — Oracle's recursive subquery factoring, not via CONNECT BY (see "
        "GAP-005 for that separate case), but via a CTE directly referencing itself after "
        "UNION [ALL]. Oracle doesn't require an explicit RECURSIVE keyword — recursion is "
        "inferred automatically from the self-reference. ora2pg copies the WITH verbatim, "
        "without adding RECURSIVE (confirmed by a real ora2pg + PostgreSQL 16 run, "
        "docs/research/gap-024-recursive-with.md). PostgreSQL requires RECURSIVE explicitly "
        "— without it, the CTE's self-reference in the second UNION branch fails: 'there is a "
        "WITH item named ..., but it cannot be referenced from this part of the query', with "
        "a 'Use WITH RECURSIVE' hint. If the query also uses a CYCLE clause, after adding "
        "RECURSIVE by hand you'll also need to move it after the CTE body's closing "
        "parenthesis and add PostgreSQL's mandatory USING clause — in Oracle, CYCLE sits "
        "before AS and doesn't need USING."
    ),
    "SQL_MACRO — функция-макрос Oracle (SQL_MACRO(SCALAR) или SQL_MACRO(TABLE), доступно с "
    "Oracle 20c), задуманная как текстовая подстановка прямо в SQL (в WHERE/FROM), а не как "
    "обычный вызов функции. ora2pg молча отбрасывает ключевое слово SQL_MACRO и конвертирует "
    "тело в обычную PL/pgSQL функцию, возвращающую строку (подтверждено реальным прогоном "
    "ora2pg + PostgreSQL 16, docs/research/gap-019-sql-macro.md). Сама функция компилируется "
    "без ошибок, но при вызове в том виде, для которого она была написана (например, прямо в "
    "WHERE как булево выражение), падает с ошибкой типа — PostgreSQL пытается использовать "
    "текстовый результат функции как boolean напрямую, а не подставить его текст в запрос как "
    "делал Oracle. Нужно вручную переписать вызывающий код, встроив логику макроса как "
    "обычное условие или подзапрос.": (
        "SQL_MACRO — an Oracle macro function (SQL_MACRO(SCALAR) or SQL_MACRO(TABLE), "
        "available since Oracle 20c), meant as a text substitution directly inside SQL (in "
        "WHERE/FROM), not as an ordinary function call. ora2pg silently drops the SQL_MACRO "
        "keyword and converts the body into an ordinary PL/pgSQL function that returns a "
        "string (confirmed by a real ora2pg + PostgreSQL 16 run, "
        "docs/research/gap-019-sql-macro.md). The function itself compiles without errors, "
        "but when called the way it was written to be used (e.g. directly in WHERE as a "
        "boolean expression), it fails with a type error — PostgreSQL tries to use the "
        "function's text result as a boolean directly, instead of substituting its text into "
        "the query the way Oracle did. The calling code needs to be manually rewritten, "
        "inlining the macro's logic as an ordinary condition or subquery."
    ),
    "PARTITION BY RANGE/LIST/HASH/REFERENCE/SYSTEM — секционирование таблицы. ora2pg "
    "полностью отбрасывает секционирование при конвертации: ни PARTITION BY, ни сами секции "
    "не попадают в вывод вообще — таблица создаётся как обычная, несекционированная "
    "(подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-013-table-partitioning.md). Совсем без предупреждения — ни в выводе, "
    "ни в --estimate_cost. Для больших таблиц это не просто синтаксическая мелочь: теряется "
    "архитектурная стратегия хранения/обслуживания (partition pruning, раздельное "
    "обслуживание партиций). PostgreSQL поддерживает декларативное партиционирование, но "
    "синтаксис отличается — секции нужно пересоздать вручную (CREATE TABLE ... PARTITION OF "
    "...).": (
        "PARTITION BY RANGE/LIST/HASH/REFERENCE/SYSTEM — table partitioning. ora2pg drops "
        "partitioning entirely during conversion: neither PARTITION BY nor the partitions "
        "themselves make it into the output — the table is created as an ordinary, "
        "unpartitioned one (confirmed by a real ora2pg + PostgreSQL 16 run, "
        "docs/research/gap-013-table-partitioning.md). No warning at all — not in the "
        "output, not in --estimate_cost. For large tables, this isn't just a syntax nitpick: "
        "an architectural storage/maintenance strategy is lost (partition pruning, "
        "per-partition maintenance). PostgreSQL supports declarative partitioning, but the "
        "syntax differs — the partitions need to be recreated by hand (CREATE TABLE ... "
        "PARTITION OF ...)."
    ),
    "WITH FUNCTION/PROCEDURE — встроенное определение функции внутри собственного "
    "WITH-предложения запроса (Oracle 12c+). ora2pg не просто копирует конструкцию как есть "
    "— он полностью разваливает структуру: вложенная функция 'утекает' наружу как отдельная "
    "функция верхнего уровня пакета, а тело содержащей её процедуры обрывается буквально на "
    "'BEGIN WITH;', теряя весь настоящий запрос (подтверждено реальным прогоном ora2pg + "
    "PostgreSQL 16, docs/research/gap-010-with-function.md). Падает уже на этапе компиляции "
    "тела функции при первом вызове (синтаксическая ошибка 'syntax error at end of input'), "
    "не просто на выполнении. Единственный путь — вручную вынести логику в обычную "
    "функцию/процедуру PostgreSQL.": (
        "WITH FUNCTION/PROCEDURE — a function defined inline inside a query's own WITH "
        "clause (Oracle 12c+). ora2pg doesn't just copy the construct verbatim — it "
        "completely breaks the structure: the nested function 'leaks' out as a separate "
        "top-level package function, and the body of the procedure that contained it gets "
        "cut off literally at 'BEGIN WITH;', losing the entire real query (confirmed by a "
        "real ora2pg + PostgreSQL 16 run, docs/research/gap-010-with-function.md). It fails "
        "at the function body's compilation stage on the first call (syntax error 'syntax "
        "error at end of input'), not just at execution. The only path is to manually move "
        "the logic out into an ordinary PostgreSQL function/procedure."
    ),
    "ROWID/UROWID как тип столбца — ora2pg конвертирует его в oid (подтверждено реальным "
    "прогоном ora2pg + PostgreSQL 16, docs/research/gap-029-rowid-urowid.md). oid — это "
    "4-байтовое целое число для внутренних идентификаторов системных объектов PostgreSQL, не "
    "имеющее ничего общего с форматом или семантикой Oracle ROWID. CREATE TABLE проходит без "
    "ошибок, но реальное значение ROWID (например 'AAAWJ0AABAAAKgaAAA') не проходит INSERT в "
    "такой столбец ('invalid input syntax for type oid') — тип-заменитель несовместим с "
    "данными, которые должен хранить. Нужно вручную выбрать подходящий тип (обычно text, если "
    "значение используется только как непрозрачный идентификатор, без арифметики или "
    "сравнения диапазонов).": (
        "ROWID/UROWID as a column's data type — ora2pg converts it to oid (confirmed by a "
        "real ora2pg + PostgreSQL 16 run, docs/research/gap-029-rowid-urowid.md). oid is a "
        "4-byte integer PostgreSQL uses for its own system objects' internal identifiers, "
        "with nothing in common with Oracle ROWID's format or semantics. CREATE TABLE runs "
        "without errors, but a real ROWID value (e.g. 'AAAWJ0AABAAAKgaAAA') fails INSERT into "
        "such a column ('invalid input syntax for type oid') — the replacement type is "
        "incompatible with the data it's supposed to hold. A suitable type needs to be chosen "
        "by hand (usually text, if the value is only ever used as an opaque identifier, with "
        "no arithmetic or range comparison)."
    ),
    "CREATE SEQUENCE ... CYCLE — после исчерпания диапазона (MAXVALUE/MINVALUE) Oracle "
    "начинает счёт заново, а не завершается ошибкой. ora2pg отбрасывает секцию CYCLE целиком "
    "(подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-030-sequence-cycle.md) — CREATE SEQUENCE проходит без ошибок, и "
    "последовательность работает идентично оригиналу ровно до момента исчерпания диапазона: "
    "'ERROR: nextval: reached maximum value of sequence'. Диапазон может исчерпаться месяцы "
    "спустя после миграции, в проде, а не при тестировании. Нужно добавить CYCLE вручную в "
    "CREATE SEQUENCE, если циклическое поведение действительно нужно.": (
        "CREATE SEQUENCE ... CYCLE — once the range is exhausted (MAXVALUE/MINVALUE), Oracle "
        "wraps around and starts counting again instead of failing. ora2pg drops the CYCLE "
        "section entirely (confirmed by a real ora2pg + PostgreSQL 16 run, "
        "docs/research/gap-030-sequence-cycle.md) — CREATE SEQUENCE runs without errors, and "
        "the sequence behaves identically to the original right up until its range is "
        "exhausted: 'ERROR: nextval: reached maximum value of sequence'. The range may not "
        "be exhausted until months after migration, in production, not during testing. CYCLE "
        "needs to be added back into CREATE SEQUENCE by hand if the wraparound behavior is "
        "actually needed."
    ),
    "DEFAULT ON NULL — в отличие от обычного DEFAULT, подставляется и тогда, когда столбцу "
    "явно передан NULL, а не только когда столбец пропущен в INSERT. ora2pg копирует секцию "
    "ON NULL в вывод как есть (подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-031-default-on-null.md) — PostgreSQL не поддерживает такой синтаксис у "
    "DEFAULT вообще. В отличие от большинства других находок здесь — это не тихая потеря "
    "поведения, а немедленный 'ERROR: syntax error at or near \"ON\"' уже на этапе применения "
    "самого CREATE TABLE. Нужно вручную переписать на BEFORE-триггер или GENERATED ALWAYS AS "
    "(COALESCE(...)) STORED.": (
        "DEFAULT ON NULL — unlike a plain DEFAULT, this is applied even when the column is "
        "explicitly given NULL, not only when it's omitted from the INSERT. ora2pg copies the "
        "ON NULL section into the output verbatim (confirmed by a real ora2pg + PostgreSQL 16 "
        "run, docs/research/gap-031-default-on-null.md) — PostgreSQL doesn't support this "
        "DEFAULT syntax at all. Unlike most other findings in this registry, this isn't a "
        "silent loss of behavior — it's an immediate 'ERROR: syntax error at or near \"ON\"' "
        "at the point CREATE TABLE itself is applied. Needs to be manually rewritten as a "
        "BEFORE trigger or GENERATED ALWAYS AS (COALESCE(...)) STORED."
    ),
    "CREATE [PUBLIC] SYNONYM — ora2pg конвертирует его в CREATE OR REPLACE VIEW, но теряет "
    "схему целевого объекта целиком: 'FOR hr.employees' становится неквалифицированным 'FROM "
    "employees' (подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-032-public-synonym.md). Когда имя синонима совпадает с базовым именем "
    "цели (самый частый случай в реальности — в этом обычно и есть весь смысл синонима), "
    "получается самоссылающийся VIEW: 'ERROR: relation ... does not exist' прямо на этапе "
    "применения DDL. Когда имена различаются, отказа не будет, но то, к какой именно таблице "
    "привяжется представление, целиком зависит от search_path в момент CREATE VIEW, а не от "
    "исходной Oracle-схемы — при миграции нескольких схем в одну базу представление может "
    "молча привязаться не к той одноимённой таблице, без единой ошибки. Нужно вручную "
    "квалифицировать целевую таблицу схемой в определении VIEW.": (
        "CREATE [PUBLIC] SYNONYM — ora2pg converts it to CREATE OR REPLACE VIEW, but drops "
        "the target object's schema entirely: 'FOR hr.employees' becomes an unqualified "
        "'FROM employees' (confirmed by a real ora2pg + PostgreSQL 16 run, "
        "docs/research/gap-032-public-synonym.md). When the synonym shares its target's base "
        "name (the common real-world convention — that's usually the entire point of a "
        "synonym), the result is a self-referencing view: 'ERROR: relation ... does not "
        "exist' right at DDL-apply time. When the names differ, there's no failure, but which "
        "table the view actually binds to depends entirely on the runtime search_path at "
        "CREATE VIEW time, not the original Oracle schema — migrating several schemas into "
        "one database can leave the view silently bound to the wrong same-named table, with "
        "no error at all. The target table needs to be manually schema-qualified in the view "
        "definition."
    ),
    "GENERATED ALWAYS AS (...) VIRTUAL — виртуальный столбец. Помимо вычисления значения, "
    "Oracle гарантирует на уровне сервера, что в такой столбец нельзя явно ничего записать "
    "(ORA-54016 при любой попытке в INSERT/UPDATE). ora2pg переносит сам расчёт корректно — "
    "через BEFORE INSERT OR UPDATE-триггер вместо нативного GENERATED ALWAYS AS (...) STORED "
    "— но эта защита теряется (подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-033-virtual-column.md): явное присваивание значения такому столбцу в "
    "INSERT/UPDATE молча проходит без единой ошибки, триггер просто подменяет переданное "
    "значение вычисленным. Итоговое значение в столбце корректно — это не потеря данных, а "
    "потеря ранней диагностики: код, по ошибке или намеренно присваивающий значение "
    "вычисляемому столбцу, в Oracle был бы пойман сразу на тестировании, после миграции "
    "проходит незамеченным.": (
        "GENERATED ALWAYS AS (...) VIRTUAL — a virtual column. Besides computing its value, "
        "Oracle guarantees at the server level that nothing can be explicitly written to such "
        "a column (ORA-54016 on any attempt in INSERT/UPDATE). ora2pg carries the computation "
        "itself over correctly — via a BEFORE INSERT OR UPDATE trigger instead of "
        "PostgreSQL's native GENERATED ALWAYS AS (...) STORED — but that protection is lost "
        "(confirmed by a real ora2pg + PostgreSQL 16 run, "
        "docs/research/gap-033-virtual-column.md): explicitly assigning a value to such a "
        "column in INSERT/UPDATE silently succeeds with no error at all, the trigger just "
        "overwrites the given value with the computed one. The column's final value is "
        "correct — this isn't data loss, it's a loss of early diagnostics: code that "
        "mistakenly (or deliberately) assigns a value to a computed column would have been "
        "caught immediately in Oracle during testing; after migration, it goes unnoticed."
    ),
    "Директивы условной компиляции PL/SQL ($IF/$ELSIF/$ELSE/$END) — препроцессор, "
    "обрабатываемый компилятором Oracle до собственно компиляции тела: код в невыбранной ветке "
    "не просто пропускается на выполнении, он вообще не компилируется. ora2pg копирует "
    "директивы в вывод буквально, как обычный текст (подтверждено реальным прогоном ora2pg + "
    "PostgreSQL 16, docs/research/gap-035-conditional-compilation.md) — у PL/pgSQL нет "
    "препроцессора условной компиляции вообще, это не валидный синтаксис ни в каком виде. "
    "CREATE PROCEDURE/FUNCTION проходит без единой ошибки (ora2pg отключает "
    "check_function_bodies в своём выводе), а падает только при первом реальном вызове — "
    "'syntax error at or near \"$\"'. Особенно коварно для веток, управляемых редко "
    "переключаемыми флагами (например режимом отладки): отказ может случиться далеко не сразу "
    "после миграции. Нужно вручную развернуть нужную ветку в обычный код (или обычный IF, если "
    "решение должно приниматься во время выполнения, а не компиляции).": (
        "Oracle PL/SQL conditional-compilation directives ($IF/$ELSIF/$ELSE/$END) — a "
        "preprocessor Oracle's compiler runs before the body is compiled at all: code in a "
        "branch that isn't selected isn't just skipped at runtime, it's never compiled in the "
        "first place. ora2pg copies the directives into the output verbatim, as plain text "
        "(confirmed by a real ora2pg + PostgreSQL 16 run, "
        "docs/research/gap-035-conditional-compilation.md) — PL/pgSQL has no conditional-"
        "compilation preprocessor at all, this isn't valid syntax in any form. CREATE "
        "PROCEDURE/FUNCTION runs without a single error (ora2pg disables "
        "check_function_bodies in its own output), it only fails on the first real call — "
        "'syntax error at or near \"$\"'. Especially treacherous for branches gated by rarely-"
        "toggled flags (e.g. a debug mode): the failure may not surface until well after "
        "migration. The needed branch needs to be manually unrolled into ordinary code (or an "
        "ordinary IF, if the decision genuinely needs to happen at runtime rather than compile "
        "time)."
    ),
    "Локально объявленная процедура/функция внутри декларативной секции другого блока "
    "(пакета, процедуры, функции). ora2pg не просто копирует её как есть — вложенная "
    "процедура/функция 'утекает' наружу как отдельный объект верхнего уровня, а содержащий её "
    "блок пропадает из вывода вообще (подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-034-nested-subprogram.md). Хуже того, тело вложенного объекта в выводе "
    "искажено — после его собственного END к нему приклеивается executable-секция содержащего "
    "блока как единый (синтаксически неверный) текст. CREATE PROCEDURE/FUNCTION проходит без "
    "единой ошибки (ora2pg отключает check_function_bodies в своём выводе), а падает только при "
    "первом реальном вызове — 'syntax error at or near \"BEGIN\"' на этапе компиляции тела. "
    "Нужно вручную вынести вложенную логику в отдельную функцию/процедуру PostgreSQL верхнего "
    "уровня.": (
        "A locally declared procedure/function inside another block's own declare section (a "
        "package, procedure, or function). ora2pg doesn't just copy it as-is — the nested "
        "procedure/function 'leaks' out as a separate top-level object, and the block that "
        "contained it disappears from the output entirely (confirmed by a real ora2pg + "
        "PostgreSQL 16 run, docs/research/gap-034-nested-subprogram.md). Worse, the nested "
        "object's own body is corrupted in the output — the containing block's executable "
        "section gets glued onto it right after its own END, as one (syntactically invalid) "
        "block of text. CREATE PROCEDURE/FUNCTION runs without a single error (ora2pg disables "
        "check_function_bodies in its own output), it only fails on the first real call — "
        "'syntax error at or near \"BEGIN\"' at body-compilation time. The nested logic needs "
        "to be manually moved out into a separate, top-level PostgreSQL function/procedure."
    ),
    "Переменная, объявленная на верхнем уровне PACKAGE BODY (не внутри конкретной процедуры/"
    "функции) — состояние на уровне сессии, общее для всех процедур пакета. ora2pg заменяет "
    "чтение/запись такой переменной на current_setting()/set_config() с пользовательским GUC-"
    "параметром — идея разумная (третий аргумент set_config — false, что соответствует времени "
    "жизни пакетной переменной в Oracle, вся сессия), но реализация сломана в двух местах "
    "(подтверждено реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-036-package-state.md). Во-первых, set_config() принимает text вторым "
    "аргументом, а ora2pg не добавляет явное приведение типа для нетекстовых переменных — "
    "'ERROR: function set_config(unknown, bigint, boolean) does not exist' при любом вызове "
    "записывающей процедуры, без исключений. Во-вторых, даже после ручного добавления "
    "приведения типа: необъявленная числовая пакетная переменная в Oracle по умолчанию NULL, а "
    "чтение ещё не установленного пользовательского GUC-параметра в PostgreSQL завершается "
    "ошибкой 'unrecognized configuration parameter', а не NULL — проявляется, когда чтение "
    "происходит раньше первой записи в той же сессии. Нужно вручную добавить приведение типа к "
    "set_config() и missing_ok => true к current_setting(), либо спроектировать состояние "
    "иначе (временная таблица, параметр приложения).": (
        "A variable declared at PACKAGE BODY top level (not inside any specific procedure/"
        "function) — session-scoped state shared across every procedure in the package. "
        "ora2pg rewrites reads/writes of such a variable into current_setting()/set_config() "
        "calls against a custom GUC parameter — a reasonable idea (set_config's third argument "
        "is false, matching a package variable's Oracle lifetime of the whole session), but "
        "the implementation is broken in two places (confirmed by a real ora2pg + PostgreSQL "
        "16 run, docs/research/gap-036-package-state.md). First, set_config() takes text as "
        "its second argument, and ora2pg adds no explicit cast for non-text variables — "
        "'ERROR: function set_config(unknown, bigint, boolean) does not exist' on any call to "
        "the writing procedure, no exceptions. Second, even after manually adding the cast: an "
        "unset numeric package variable defaults to NULL in Oracle, while reading an as-yet-"
        "unset custom GUC parameter in PostgreSQL fails with 'unrecognized configuration "
        "parameter' instead of returning NULL — surfaces whenever a read happens before the "
        "first write in the same session. The cast needs to be added to set_config() by hand, "
        "along with missing_ok => true on current_setting(), or the state needs to be designed "
        "differently (a temp table, an application parameter)."
    ),
    "CREATE TABLE ... ORGANIZATION INDEX — индекс-организованная таблица (IOT): данные "
    "физически хранятся в структуре первичного ключа, а не в отдельной куче со ссылками на неё "
    "из индекса. ora2pg отбрасывает секцию ORGANIZATION INDEX целиком — таблица "
    "конвертируется как обычная куча с отдельным индексом по первичному ключу (подтверждено "
    "реальным прогоном ora2pg + PostgreSQL 16, "
    "docs/research/gap-037-index-organized-table.md). Не синтаксическая ошибка и не потеря "
    "данных — ограничения целостности сохраняются, таблица работает корректно. Теряется "
    "архитектурная характеристика хранения: у PostgreSQL нет настоящих индекс-организованных "
    "таблиц (обычный PRIMARY KEY всегда создаёт отдельный индекс над отдельной кучей) — для "
    "производительность-чувствительных таблиц-кэшей, изначально спроектированных как IOT "
    "именно ради этого свойства, стоит перепроверить производительность на реальной нагрузке "
    "после миграции.": (
        "CREATE TABLE ... ORGANIZATION INDEX — an index-organized table (IOT): data lives "
        "physically inside the primary key's own structure, not in a separate heap the index "
        "points into. ora2pg drops the ORGANIZATION INDEX section entirely — the table "
        "converts as an ordinary heap table with a separate primary-key index (confirmed by a "
        "real ora2pg + PostgreSQL 16 run, docs/research/gap-037-index-organized-table.md). Not "
        "a syntax error and not data loss — integrity constraints are preserved, the table "
        "works correctly. A storage architecture characteristic is lost: PostgreSQL has no "
        "true index-organized tables (an ordinary PRIMARY KEY always creates a separate index "
        "over a separate heap) — for performance-sensitive lookup/cache tables originally "
        "designed as an IOT for exactly that property, worth re-checking performance under "
        "real load after migration."
    ),
}


# Per-detector remediation hint, English counterpart of terminal_report.py's
# _REMEDIATION_HINT. Keyed by detector name (not message text) since every
# detector has exactly one hint regardless of how many message variants it
# emits (unlike EXPLANATION_EN above).
REMEDIATION_HINT_EN: dict[str, str] = {
    "autonomous_tx": "Review the dblink migration by hand — the network dependency may be "
    "unacceptable in an isolated environment",
    "compound_triggers": "Split into separate ordinary triggers (BEFORE/AFTER × STATEMENT/ROW) "
    "sharing state via a table",
    "dbms_utl_calls": "Rewrite by hand, or use the orafce extension if it has an equivalent "
    "for this call",
    "connect_by": "Replace LEVEL with a real counter column in the generated WITH RECURSIVE",
    "merge_delete_clause": "Split the MERGE into two WHEN MATCHED branches with mutually "
    "exclusive conditions instead of DELETE WHERE",
    "bulk_collect": "Rewrite TYPE/BULK COLLECT as a PostgreSQL array (type[]) or a temporary "
    "table; rewrite FORALL as a loop or UNNEST()",
    "database_link": "Set up postgres_fdw/dblink with the remote database's real connection "
    "parameters instead of @dblink_name",
    "model_clause": "Rewrite by hand using window functions or recursive CTEs — PostgreSQL "
    "has no direct MODEL equivalent",
    "pivot_clause": "Rewrite as conditional aggregation (FILTER/CASE WHEN) or the tablefunc "
    "extension (crosstab())",
    "object_type": "Rewrite as a composite type plus separate functions — PostgreSQL has no "
    "object types with methods",
    "with_function": "Manually move the inline function out into an ordinary PostgreSQL "
    "function/procedure — ora2pg breaks the query's structure",
    "flashback_query": "Design a separate history/audit mechanism — PostgreSQL has no direct "
    "AS OF equivalent",
    "global_temp_table": "Add 'ON COMMIT DELETE ROWS' to the temporary table definition by "
    "hand — ora2pg drops the ON COMMIT section",
    "table_partitioning": "Recreate the partitions by hand (CREATE TABLE ... PARTITION OF "
    "...) — ora2pg drops partitioning entirely",
    "connect_by_nocycle": "Rewrite fully by hand as WITH RECURSIVE — converting NOCYCLE/ORDER "
    "SIBLINGS BY breaks the block's structure",
    "context_object": "Rewrite using current_setting()/set_config() or Row-Level Security "
    "(CREATE POLICY) — there's no direct CREATE CONTEXT equivalent",
    "insert_all": "Split into a set of separate INSERT INTO ... SELECT ... statements, one "
    "per WHEN/INTO branch",
    "json_table": "Rewrite using jsonb_to_recordset()/jsonb_array_elements() with explicit "
    "type casts",
    "external_table": "Set up a foreign table via file_fdw (or an fdw for the format needed) "
    "— ora2pg turns it into an ordinary table",
    "sql_macro": "Inline the macro's logic as an ordinary condition/subquery directly in the "
    "calling code — SQL_MACRO converts to an ordinary function",
    "invisible_column": "Explicitly list columns in SELECT/INSERT wherever the hiding "
    "mattered — PostgreSQL has no INVISIBLE equivalent",
    "collection_type": "Rewrite as a built-in array (datatype[]) or a separate linked table "
    "— ora2pg drops the collection type declaration entirely",
    "cross_apply": "Rewrite as JOIN LATERAL (...) ON true / LEFT JOIN LATERAL (...) ON true "
    "— PostgreSQL has no APPLY syntax",
    "oracle_text": "Rewrite using tsvector/tsquery plus a GIN index (to_tsvector/@@) — ora2pg "
    "drops INDEXTYPE and doesn't migrate CONTAINS/CATSEARCH/MATCHES",
    "recursive_with": "Add the RECURSIVE keyword by hand (and, if CYCLE is present, move it "
    "after the CTE body and add the mandatory USING clause)",
    "invisible_index": "Check whether the index genuinely needs to stay hidden from the "
    "optimizer — PostgreSQL has no INVISIBLE equivalent for indexes",
    "read_only_table": "Set up REVOKE INSERT/UPDATE/DELETE from all roles, or a BEFORE "
    "trigger that rejects DML — ora2pg drops the READ ONLY section",
    "materialized_view_log": "Design materialized view refreshes around a full REFRESH "
    "MATERIALIZED VIEW — PostgreSQL has no incremental FAST REFRESH",
    "identity_column": "Remove the extra outer pair of parentheses around the sequence "
    "options by hand — an ora2pg substitution bug, not a skipped conversion",
    "rowid_type": "Manually pick a suitable type (usually text) for any column ora2pg "
    "converted from ROWID/UROWID to oid",
    "sequence_cycle": "Add CYCLE back into CREATE SEQUENCE by hand if wraparound behavior is "
    "actually needed",
    "default_on_null": "Manually rewrite as a BEFORE trigger or GENERATED ALWAYS AS "
    "(COALESCE(...)) STORED — PostgreSQL has no DEFAULT ... ON NULL equivalent",
    "public_synonym": "Manually schema-qualify the target table in the generated VIEW's "
    "definition",
    "virtual_column": "Be aware the generated trigger silently discards any value explicitly "
    "assigned to the column — add application-level validation if that protection matters",
    "conditional_compilation": "Manually unroll the needed branch into ordinary code (or an "
    "ordinary IF for a runtime decision) — PostgreSQL has no conditional-compilation "
    "preprocessor",
    "nested_subprogram": "Manually move the nested logic out into a separate, top-level "
    "PostgreSQL function/procedure",
    "package_state": "Add an explicit ::text cast to set_config() and missing_ok => true to "
    "current_setting(), or design the state differently (a temp table, an application "
    "parameter)",
    "index_organized_table": "Re-check performance under real load — PostgreSQL has no true "
    "index-organized tables, the converted table is an ordinary heap with a separate index",
}


def translate_message(message: str, lang: str) -> str:
    """The single point where a Finding's Russian message gets swapped for
    its English counterpart, if lang == "en" and a translation exists.
    Called once, centrally, on the finding list before it's handed to any
    renderer (terminal/markdown/json/csv/sarif/html) -- so every output
    format gets consistent language for the message field without each
    renderer needing its own translation logic. Falls back to the original
    Russian text if no translation is registered (should only happen for a
    third-party detector added without going through this module -- see
    scripts/doctor.py's parity check for why this shouldn't happen for any
    detector shipped in this project)."""
    if lang != "en":
        return message
    return EXPLANATION_EN.get(message, message)
