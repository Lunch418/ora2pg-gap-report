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
    "explain_severity_line": {"ru": "Severity: {severity}", "en": "Severity: {severity}"},
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
        "--check-connect-by, --verify, --fix, --write, --format, --output, --severity или "
        "--object[/red]",
        "en": "[red]--explain is a standalone documentation lookup, not a scan: it can't be "
        "combined with file paths, --fail-on, --save, --baseline, --check-connect-by, "
        "--verify, --fix, --write, --format, --output, --severity, or --object[/red]",
    },
    "tui_conflict_error": {
        "ru": "[red]--tui — самостоятельный интерактивный режим: принимает не больше одного "
        "пути (стартовая точка в дереве) и не сочетается с --explain, --verify, --fix, "
        "--write, --fail-on, --save, --baseline, --check-connect-by, --severity, --object, "
        "--format или --output[/red]",
        "en": "[red]--tui is a standalone interactive mode: it takes at most one path (a "
        "starting point for the tree) and can't be combined with --explain, --verify, "
        "--fix, --write, --fail-on, --save, --baseline, --check-connect-by, --severity, "
        "--object, --format, or --output[/red]",
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
        "с --explain, --save, --fail-on, --check-connect-by, --fix, --write, --severity "
        "или --object[/red]",
        "en": "[red]--verify is a standalone baseline-comparison mode, it can't be "
        "combined with --explain, --save, --fail-on, --check-connect-by, --fix, --write, "
        "--severity, or --object[/red]",
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
    # --fix (mechanical autofix of ora2pg's generated output, see autofix.py)
    "fix_conflict_error": {
        "ru": "[red]--fix — отдельный режим исправления сгенерированного кода, его нельзя "
        "сочетать с --explain, --verify, --tui, --fail-on, --save, --baseline, "
        "--check-connect-by, --severity, --object, --format или --output[/red]",
        "en": "[red]--fix is a standalone mode for fixing generated code, it can't be "
        "combined with --explain, --verify, --tui, --fail-on, --save, --baseline, "
        "--check-connect-by, --severity, --object, --format, or --output[/red]",
    },
    "fix_write_without_fix_error": {
        "ru": "[red]--write работает только вместе с --fix[/red]",
        "en": "[red]--write only makes sense together with --fix[/red]",
    },
    "fix_diff_header": {
        "ru": "[cyan]{path}[/cyan]: найдено исправлений — {count}",
        "en": "[cyan]{path}[/cyan]: fixes found — {count}",
    },
    "fix_summary_clean": {
        "ru": "{path}: исправлений не найдено",
        "en": "{path}: no fixes found",
    },
    "fix_summary_written": {
        "ru": "[green]{path}: записано, исправлений — {count}[/green]",
        "en": "[green]{path}: written, fixes applied — {count}[/green]",
    },
    "fix_summary_dry_run_hint": {
        "ru": "[yellow]Показан diff, файлы не изменены. Добавьте --write для реальной "
        "перезаписи.[/yellow]",
        "en": "[yellow]Diff shown, files unchanged. Add --write to actually rewrite "
        "them.[/yellow]",
    },
    "fix_write_error": {
        "ru": "[red]Не удалось записать {path}: {exc}[/red]",
        "en": "[red]Couldn't write {path}: {exc}[/red]",
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
    "help_dialect": {
        "ru": "Диалект исходного кода: oracle (по умолчанию), mysql (дампы MySQL/MariaDB, "
        "source-side для ora2pg -m) или mssql (скрипты T-SQL/SQL Server, source-side для "
        "ora2pg -M). Работает только для обычного сканирования — не сочетается с --tui, "
        "--explain, --verify, --fix.",
        "en": "Source dialect: oracle (default), mysql (MySQL/MariaDB dumps, the source "
        "side of ora2pg -m) or mssql (T-SQL/SQL Server scripts, the source side of "
        "ora2pg -M). Only applies to a plain scan -- cannot be combined with --tui, "
        "--explain, --verify, --fix.",
    },
    "dialect_verify_unsupported_error": {
        "ru": "--verify пока поддерживает только --dialect oracle: пере-сканирование "
        "сгенерированного вывода по MySQL-детекторам ещё не реализовано.",
        "en": "--verify only supports --dialect oracle for now: re-scanning generated "
        "output with MySQL detectors isn't implemented yet.",
    },
    "dialect_fix_unsupported_error": {
        "ru": "--fix пока поддерживает только --dialect oracle: автофиксов для MySQL-"
        "находок ещё нет.",
        "en": "--fix only supports --dialect oracle for now: there are no autofixes for "
        "MySQL findings yet.",
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
    "help_fix": {
        "ru": "Применить известные механические исправления к сгенерированному ora2pg "
        "PostgreSQL-коду (не к Oracle-исходнику — как --verify, читает пути как результат "
        "миграции). Сейчас единственное исправление — двойные скобки в GENERATED ... AS "
        "IDENTITY (...) (GAP-028). По умолчанию ничего не меняет на диске, только печатает "
        "unified diff; для реальной перезаписи файлов добавьте --write. Самостоятельный "
        "режим — не сочетается с --explain/--verify/--tui/--fail-on/--save/--baseline/"
        "--check-connect-by/--severity/--object/--format/--output.",
        "en": "Apply known mechanical fixes to ora2pg's *generated* PostgreSQL code (not "
        "Oracle source -- like --verify, reads paths as post-migration output). Currently "
        "the only fix is the double-paren bug in GENERATED ... AS IDENTITY (...) "
        "(GAP-028). Prints a unified diff by default, without touching anything on disk; "
        "add --write to actually rewrite the files. A standalone mode -- not combinable "
        "with --explain/--verify/--tui/--fail-on/--save/--baseline/--check-connect-by/"
        "--severity/--object/--format/--output.",
    },
    "help_write": {
        "ru": "Вместе с --fix: реально перезаписать файлы на диске вместо печати diff. "
        "Без --fix ни на что не влияет.",
        "en": "With --fix: actually rewrite the files on disk instead of printing a diff. "
        "Has no effect without --fix.",
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
    'MATCH_RECOGNIZE (Oracle 12c+) — сопоставление строк с шаблоном прямо в SQL (PARTITION BY / ORDER BY / MEASURES / PATTERN / DEFINE): поиск последовательностей строк, соответствующих регулярному выражению над потоком, для анализа трендов, сессий, последовательностей событий. ora2pg копирует конструкцию в вывод как есть, без изменений (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-038-match-recognize.md). У PostgreSQL нет никакого аналога row pattern matching — падает синтаксической ошибкой уже при загрузке сгенерированного DDL. Переписывается вручную через оконные функции (LAG/LEAD над разделами) плюс фильтрацию, либо через рекурсивный CTE — прямой замены на одну конструкцию не существует.': (
        'MATCH_RECOGNIZE (Oracle 12c+) — row pattern matching directly in SQL (PARTITION BY / '
        'ORDER BY / MEASURES / PATTERN / DEFINE): finding sequences of rows that match a '
        'regular-expression-like pattern over an ordered stream, used for trend, session and '
        'event-sequence analysis. ora2pg copies the clause into its output unchanged '
        '(confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, '
        'docs/research/gap-038-match-recognize.md). PostgreSQL has no row pattern matching of '
        'any kind — the generated DDL fails to load with a syntax error. Rewritten by hand '
        'using window functions (LAG/LEAD over the partition) plus filtering, or a recursive '
        'CTE — there is no single-construct replacement.'
    ),
    'CONNECT_BY_ROOT / CONNECT_BY_ISLEAF / CONNECT_BY_ISCYCLE — иерархические операторы и псевдостолбцы Oracle: корневое значение ветки, признак листа, признак цикла. ora2pg разворачивает сам CONNECT BY в WITH RECURSIVE, но эти три конструкции переносит в сгенерированный код как есть, без замены (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-039-connect-by-pseudocolumn.md). PostgreSQL их не знает — падает при загрузке (синтаксическая ошибка на CONNECT_BY_ROOT, «column does not exist» на ISLEAF/ISCYCLE). Переписывается вручную: корень ветки протаскивается через дополнительный столбец рекурсивного CTE, признак листа считается отдельным NOT EXISTS-подзапросом, признак цикла — через CYCLE-секцию рекурсивного CTE (PostgreSQL 14+). Отдельно: SYS_CONNECT_BY_PATH этим детектором НЕ помечается — его ora2pg конвертирует корректно.': (
        "CONNECT_BY_ROOT / CONNECT_BY_ISLEAF / CONNECT_BY_ISCYCLE — Oracle's hierarchical "
        "operator and pseudocolumns: the branch's root value, the leaf flag, the cycle flag. "
        'ora2pg does expand the surrounding CONNECT BY into a WITH RECURSIVE, but carries '
        'these three through into the generated code unchanged (confirmed against a real '
        'ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-039-connect-by-pseudocolumn.md). '
        "PostgreSQL doesn't know them — it fails at load time (a syntax error on "
        'CONNECT_BY_ROOT, "column does not exist" on ISLEAF/ISCYCLE). Rewritten by hand: '
        'carry the branch root through an extra recursive-CTE column, compute the leaf flag '
        "with a NOT EXISTS subquery, and the cycle flag with the CTE's own CYCLE clause "
        '(PostgreSQL 14+). Note: SYS_CONNECT_BY_PATH is deliberately NOT flagged by this '
        'detector — ora2pg converts that one correctly.'
    ),
    'KEEP (DENSE_RANK FIRST/LAST ORDER BY ...) — Oracle-специфичный вариант агрегатной функции: взять значение агрегата не по всей группе, а по строке, первой (или последней) в заданном порядке внутри группы (классика — «зарплата самого раннего нанятого в отделе»). ora2pg копирует конструкцию в вывод как есть (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-040-keep-dense-rank.md). У PostgreSQL нет KEEP-синтаксиса — падает синтаксической ошибкой при загрузке. Переписывается вручную: чаще всего через оконную функцию FIRST_VALUE/LAST_VALUE с той же ORDER BY в OVER-разделе, либо через DISTINCT ON, либо через агрегаты PostgreSQL с FILTER.': (
        "KEEP (DENSE_RANK FIRST/LAST ORDER BY ...) — Oracle's aggregate modifier that takes "
        'the aggregate not over the whole group but over the row that comes first (or last) '
        'in a given order within that group (the classic case: "the salary of the earliest '
        'hire in each department"). ora2pg copies the construct into its output unchanged '
        '(confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, '
        'docs/research/gap-040-keep-dense-rank.md). PostgreSQL has no KEEP syntax — it fails '
        'to load with a syntax error. Rewritten by hand: usually a FIRST_VALUE/LAST_VALUE '
        'window function with the same ORDER BY inside OVER, or DISTINCT ON, or a PostgreSQL '
        'aggregate with FILTER.'
    ),
    "Операторы над коллекциями Oracle — CAST(MULTISET(...)), MULTISET UNION/INTERSECT/EXCEPT, MEMBER OF, SUBMULTISET OF: работа с вложенными таблицами и VARRAY как со множествами прямо в SQL. ora2pg копирует эти конструкции в вывод как есть, без изменений (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-041-multiset-operator.md). У PostgreSQL нет ни одного из этих операторов — падает синтаксической ошибкой при загрузке. Переписывается вручную под модель массивов PostgreSQL: CAST(MULTISET(...)) → ARRAY(SELECT ...), MULTISET UNION → оператор || над массивами или отдельный UNION-подзапрос, MEMBER OF → '= ANY(массив)', SUBMULTISET OF → оператор <@ над массивами.": (
        "Oracle's collection operators — CAST(MULTISET(...)), MULTISET "
        'UNION/INTERSECT/EXCEPT, MEMBER OF, SUBMULTISET OF: treating nested tables and '
        'VARRAYs as sets directly in SQL. ora2pg copies these constructs into its output '
        'unchanged (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, '
        'docs/research/gap-041-multiset-operator.md). PostgreSQL has none of these operators '
        "— it fails to load with a syntax error. Rewritten by hand against PostgreSQL's array "
        'model: CAST(MULTISET(...)) → ARRAY(SELECT ...), MULTISET UNION → the || operator '
        "over arrays or a separate UNION subquery, MEMBER OF → '= ANY(array)', SUBMULTISET OF "
        '→ the <@ operator over arrays.'
    ),
    'SAMPLE (n) / SAMPLE BLOCK (n) — выборка случайного процента строк (или блоков) таблицы прямо во FROM, Oracle-специфичный синтаксис. ora2pg копирует конструкцию в вывод как есть (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-042-sample-clause.md). У PostgreSQL есть своя выборка, но с другим синтаксисом и другим местом в запросе — TABLESAMPLE BERNOULLI (n) / TABLESAMPLE SYSTEM (n) — поэтому скопированный как есть Oracle-вариант падает синтаксической ошибкой при загрузке. Переписывается вручную: SAMPLE (n) → TABLESAMPLE BERNOULLI (n) (построчная выборка, ближе к Oracle SAMPLE), SAMPLE BLOCK (n) → TABLESAMPLE SYSTEM (n) (поблочная, быстрее, но статистически грубее).': (
        "SAMPLE (n) / SAMPLE BLOCK (n) — selecting a random percentage of a table's rows (or "
        'blocks) directly in the FROM clause, Oracle-specific syntax. ora2pg copies the '
        'construct into its output unchanged (confirmed against a real ora2pg 25.0 + '
        'PostgreSQL 16 run, docs/research/gap-042-sample-clause.md). PostgreSQL has its own '
        'sampling, but with different syntax and a different position in the query — '
        'TABLESAMPLE BERNOULLI (n) / TABLESAMPLE SYSTEM (n) — so the verbatim-copied Oracle '
        'form fails to load with a syntax error. Rewritten by hand: SAMPLE (n) → TABLESAMPLE '
        "BERNOULLI (n) (per-row sampling, closer to Oracle's SAMPLE), SAMPLE BLOCK (n) → "
        'TABLESAMPLE SYSTEM (n) (per-block, faster but statistically coarser).'
    ),
    'ACCESSIBLE BY (Oracle 12c+) — «белый список» вызывающих: подпрограмма объявляется доступной только перечисленным пакетам/процедурам, остальные получают ошибку компиляции при попытке её вызвать. Это средство инкапсуляции внутри схемы, работающее поверх обычных GRANT. ora2pg копирует секцию в вывод как есть, прямо в заголовок функции (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-043-accessible-by.md). PostgreSQL такого синтаксиса не знает — CREATE PROCEDURE/FUNCTION падает синтаксической ошибкой уже при загрузке. Прямого аналога нет: ограничение «кто именно из кода может вызвать» в PostgreSQL не выражается — ближайшее по смыслу решение это вынести подпрограмму в отдельную схему и раздать права через GRANT/REVOKE, что даёт защиту на уровне ролей, а не на уровне конкретных вызывающих подпрограмм.': (
        'ACCESSIBLE BY (Oracle 12c+) — a caller whitelist: the subprogram is declared '
        'accessible only to the listed packages/procedures, and anything else gets a compile '
        'error when it tries to call it. This is intra-schema encapsulation layered on top of '
        'ordinary GRANTs. ora2pg copies the clause into its output verbatim, right into the '
        'function header (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, '
        'docs/research/gap-043-accessible-by.md). PostgreSQL has no such syntax — CREATE '
        'PROCEDURE/FUNCTION fails with a syntax error at load time. There is no direct '
        'equivalent: "which code specifically may call this" isn\'t expressible in PostgreSQL '
        '— the closest approach is moving the subprogram into its own schema and controlling '
        'access with GRANT/REVOKE, which protects at the role level rather than per calling '
        'subprogram.'
    ),
    'TIMESTAMP WITH LOCAL TIME ZONE — Oracle хранит момент времени в нормализованном виде и на чтении автоматически пересчитывает его в часовой пояс текущей сессии. ora2pg конвертирует такой столбец в простой timestamp — БЕЗ часового пояса (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-044-local-time-zone.md). Ошибки не будет никогда: CREATE TABLE проходит, INSERT проходит, SELECT возвращает значение. Но пересчёт в часовой пояс сессии молча исчезает — одно и то же значение теперь отдаётся одинаковым во всех сессиях, независимо от их TIME ZONE, тогда как в Oracle оно сдвигалось. Для системы, где клиенты в разных поясах, это тихое расхождение в данных, которое проявится только как жалоба пользователя на неверное время. Правильная замена в PostgreSQL — timestamptz (timestamp with time zone): именно он делает то же, что Oracle LTZ.': (
        'TIMESTAMP WITH LOCAL TIME ZONE — Oracle stores the instant normalised and '
        "automatically converts it into the current session's time zone on read. ora2pg "
        'converts such a column into a plain timestamp — WITHOUT any time zone (confirmed '
        'against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-044-local-time- '
        'zone.md). No error is ever raised: CREATE TABLE succeeds, INSERT succeeds, SELECT '
        'returns a value. But the session-time-zone conversion silently disappears — the same '
        'value now comes back identical in every session regardless of its TIME ZONE, where '
        'in Oracle it would have shifted. For a system with clients in different time zones '
        'this is a silent data discrepancy that surfaces only as a user complaining about '
        'wrong times. The faithful PostgreSQL replacement is timestamptz (timestamp with time '
        "zone): it does exactly what Oracle's LTZ does."
    ),
    "PERIOD FOR (Oracle 12c Temporal Validity) — объявление периода действительности строки: таблица получает пару границ времени и возможность запрашивать состояние «как было на дату» через AS OF PERIOD FOR. ora2pg не просто отбрасывает секцию — он разрушает её остатком, вставляя в список столбцов обрубок 'period FOR' (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-045-temporal-validity.md). Сгенерированный CREATE TABLE падает синтаксической ошибкой уже при загрузке — то есть теряется не только сама фича, ломается создание всей таблицы. У PostgreSQL нет встроенной temporal validity; переписывается вручную: обычная пара timestamp-столбцов плюс фильтрация по ним в запросах (или расширение с типом tstzrange и ограничением-исключением, если нужен контроль пересечений).": (
        "PERIOD FOR (Oracle 12c Temporal Validity) — declaring a row's validity period: the "
        'table gets a pair of time boundaries and the ability to query "as it was on date X" '
        "via AS OF PERIOD FOR. ora2pg doesn't merely drop the clause — it corrupts the "
        "statement with a leftover, emitting a truncated 'period FOR' fragment into the "
        'column list (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, '
        'docs/research/gap-045-temporal-validity.md). The generated CREATE TABLE fails to '
        "load with a syntax error — so it isn't just the feature that's lost, creating the "
        'whole table breaks. PostgreSQL has no built-in temporal validity; rewritten by hand '
        'as an ordinary pair of timestamp columns plus filtering in queries (or a tstzrange '
        'column with an exclusion constraint, if overlap control is needed).'
    ),
    'CREATE BITMAP INDEX — битовый индекс Oracle, рассчитанный на столбцы малой кардинальности (пол, статус, флаг) и на комбинирование нескольких таких индексов побитовыми операциями. ora2pg заменяет его на \'CREATE INDEX ... USING gin(...)\' (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-046-bitmap-index.md). Для обычного скалярного столбца это не работает: PostgreSQL падает при загрузке с \'data type ... has no default operator class for access method "gin"\' — у gin по умолчанию нет класса операторов ни для varchar, ни для чисел, он рассчитан на составные типы (массивы, jsonb, tsvector). То есть индекс не просто станет другим по характеристикам — его создание не пройдёт вообще. У PostgreSQL нет битовых индексов как типа; на практике замена — обычный btree (планировщик умеет комбинировать несколько btree через bitmap scan самостоятельно, во время выполнения), либо gin с явным классом операторов из расширения btree_gin, если комбинирование нужно на уровне самого индекса.': (
        "CREATE BITMAP INDEX — Oracle's bitmap index, designed for low-cardinality columns "
        '(gender, status, a flag) and for combining several such indexes with bitwise '
        "operations. ora2pg replaces it with 'CREATE INDEX ... USING gin(...)' (confirmed "
        'against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-046-bitmap- '
        "index.md). For an ordinary scalar column that doesn't work: PostgreSQL fails at load "
        'time with \'data type ... has no default operator class for access method "gin"\' — '
        "GIN has no default operator class for varchar or numeric, it's designed for "
        "composite types (arrays, jsonb, tsvector). So the index doesn't merely end up with "
        'different characteristics — it fails to be created at all. PostgreSQL has no bitmap '
        'index as an index type; in practice the replacement is a plain btree (the planner '
        'can combine several btrees via a bitmap scan on its own, at execution time), or gin '
        'with an explicit operator class from the btree_gin extension if the combining is '
        'needed at the index level.'
    ),
    "CREATE TABLE ... OF <тип> — объектная таблица Oracle: каждая строка является экземпляром объектного типа, а атрибуты типа становятся столбцами таблицы. ora2pg не конвертирует конструкцию и не отбрасывает её — он разрушает структуру таблицы: ключевое слово OF попадает в вывод как ИМЯ СТОЛБЦА, а объявления ограничений (например 'person_id PRIMARY KEY') теряются целиком (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-047-object-table.md). Самое опасное здесь в том, что при существующем в целевой базе типе загрузка проходит БЕЗ ОШИБКИ: создаётся таблица с единственным столбцом по имени 'of' и без первичного ключа. Миграция выглядит успешной, а таблица молча имеет неверную структуру. Переписывается вручную: объектная таблица разворачивается в обычную таблицу с отдельным столбцом на каждый атрибут типа плюс явные ограничения.": (
        'CREATE TABLE ... OF <type> — an Oracle object table: every row is an instance of an '
        "object type, and the type's attributes become the table's columns. ora2pg neither "
        "converts the construct nor drops it — it corrupts the table's structure: the OF "
        'keyword ends up in the output as a COLUMN NAME, and the constraint declarations '
        "(e.g. 'person_id PRIMARY KEY') are lost entirely (confirmed against a real ora2pg "
        '25.0 + PostgreSQL 16 run, docs/research/gap-047-object-table.md). The most dangerous '
        'part is that when the type does exist in the target database, the load succeeds WITH '
        "NO ERROR: it creates a table with a single column named 'of' and no primary key. The "
        'migration looks successful while the table silently has the wrong structure. '
        'Rewritten by hand: expand the object table into an ordinary table with a separate '
        'column per type attribute plus explicit constraints.'
    ),
    'IGNORE NULLS / RESPECT NULLS — оговорка обработки NULL у аналитических функций Oracle (LAG, LEAD, FIRST_VALUE, LAST_VALUE, NTH_VALUE). ora2pg копирует её в вывод как есть (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-048-ignore-nulls.md). В PostgreSQL 16 такого синтаксиса нет ни в каком виде, поэтому запрос падает синтаксической ошибкой прямо на слове IGNORE/RESPECT. Переписывается вручную, и это не косметика: IGNORE NULLS нужно эмулировать — обычно через агрегат с FILTER, через дополнительный проход оконной функцией по «последнему не-NULL» (count(col) FILTER (WHERE col IS NOT NULL) как группирующий ключ + first_value внутри группы) или через боковой подзапрос.': (
        'IGNORE NULLS / RESPECT NULLS — the null-treatment clause on Oracle\'s analytic functions (LAG, LEAD, FIRST_VALUE, LAST_VALUE, NTH_VALUE). ora2pg copies it into its output unchanged (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-048-ignore-nulls.md). PostgreSQL 16 has no such syntax in any form, so the query fails with a syntax error right at the IGNORE/RESPECT keyword. Rewriting it by hand is more than cosmetic: IGNORE NULLS has to be emulated — usually with an aggregate plus FILTER, with a second window pass over the "last non-NULL" value (count(col) FILTER (WHERE col IS NOT NULL) as a grouping key plus first_value within the group), or with a lateral subquery.'
    ),
    'NLSSORT(...) — задание порядка сортировки по правилам конкретного языка. ora2pg переписывает вызов в PostgreSQL-овую оговорку COLLATE, подставляя имя языка из NLS_SORT прямо как имя collation: NLSSORT(name, \'NLS_SORT=GERMAN\') превращается в name COLLATE "GERMAN" (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-049-nlssort.md). Имена сортировок у Oracle и PostgreSQL не совпадают: в PostgreSQL нет collation с именем GERMAN, и запрос падает с ошибкой \'collation "GERMAN" for encoding "UTF8" does not exist\'. Нужно вручную сопоставить каждое Oracle-имя с реальной локалью PostgreSQL (для немецкого — "de-DE-x-icu" или "de_DE.utf8", в зависимости от того, собран ли сервер с ICU) и при необходимости создать её через CREATE COLLATION.': (
        'NLSSORT(...) — sorting by a specific language\'s collation rules. ora2pg rewrites the call into PostgreSQL\'s COLLATE clause, substituting the language name from NLS_SORT directly as the collation name: NLSSORT(name, \'NLS_SORT=GERMAN\') becomes name COLLATE "GERMAN" (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-049-nlssort.md). Oracle and PostgreSQL collation names do not match: PostgreSQL has no collation called GERMAN, and the query fails with \'collation "GERMAN" for encoding "UTF8" does not exist\'. Each Oracle name has to be mapped by hand onto a real PostgreSQL locale (for German, "de-DE-x-icu" or "de_DE.utf8", depending on whether the server was built with ICU) and created with CREATE COLLATION where necessary.'
    ),
    'LONG RAW — унаследованный двоичный тип Oracle. ora2pg объявляет для него отображение \'LONG RAW:bytea\' и в своей документации, и в коде (lib/Ora2Pg/Oracle.pm), но при конвертации DDL из файла столбец превращается в text, а не в bytea (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-050-long-raw-type.md). То есть это расхождение самого ora2pg с собственной документацией, а не сознательный выбор. CREATE TABLE проходит чисто, и проблема всплывает уже на переносе данных: в text нельзя положить произвольные байты — нулевой байт или любая последовательность, не являющаяся корректным UTF-8, даёт \'invalid byte sequence for encoding "UTF8"\' (для сравнения: RAW(n) и BLOB тот же ora2pg в том же прогоне отображает в bytea правильно). Тип столбца нужно поправить на bytea вручную.': (
        'LONG RAW — Oracle\'s legacy binary type. ora2pg declares the mapping \'LONG RAW:bytea\' both in its documentation and in its code (lib/Ora2Pg/Oracle.pm), yet when converting DDL from a file the column comes out as text rather than bytea (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-050-long-raw-type.md). This is ora2pg disagreeing with its own documentation, not a deliberate choice. CREATE TABLE loads cleanly and the problem surfaces during the data migration instead: arbitrary bytes cannot go into a text column — a zero byte, or any sequence that is not valid UTF-8, produces \'invalid byte sequence for encoding "UTF8"\' (for comparison, the same ora2pg run maps RAW(n) and BLOB to bytea correctly). The column type has to be corrected to bytea by hand.'
    ),
    'SYS.ANYDATA / ANYDATASET / ANYTYPE — самоописывающийся контейнер Oracle, способный хранить значение любого типа вместе с информацией о самом типе. ora2pg переносит имя типа в вывод как есть (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-051-anydata-type.md). В PostgreSQL нет ни такого типа, ни схемы SYS, поэтому CREATE TABLE падает сразу на загрузке — \'schema "sys" does not exist\' для квалифицированной записи или \'type "anydata" does not exist\' для короткой. Механической замены нет: обычно столбец переразмечают в jsonb (если важно хранить произвольную структуру) либо разносят на несколько типизированных столбцов с признаком типа, если реально хранились два-три конкретных варианта.': (
        'SYS.ANYDATA / ANYDATASET / ANYTYPE — Oracle\'s self-describing container, able to hold a value of any type together with information about that type. ora2pg carries the type name into its output unchanged (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-051-anydata-type.md). PostgreSQL has neither such a type nor a SYS schema, so CREATE TABLE fails immediately at load time — \'schema "sys" does not exist\' for the qualified spelling, \'type "anydata" does not exist\' for the short one. There is no mechanical replacement: the column is usually remodelled as jsonb (when storing arbitrary structure really is the point) or split into several typed columns plus a discriminator, if in practice only two or three concrete variants were ever stored.'
    ),
    "Системный триггер (ON DATABASE / ON SCHEMA) — триггер Oracle не на таблицу, а на событие базы или схемы: LOGON, LOGOFF, SERVERERROR, DDL, STARTUP и т. п. ora2pg переносит его как обычный табличный триггер, подставляя слово database/schema на место имени таблицы: получается 'CREATE TRIGGER ... AFTER LOGON ON database FOR EACH ROW' (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-052-system-trigger.md). PostgreSQL падает синтаксической ошибкой прямо на названии события. Прямого аналога нет ни для одного из них: DDL-события покрываются событийными триггерами PostgreSQL (CREATE EVENT TRIGGER ... ON ddl_command_end), а LOGON/LOGOFF/SERVERERROR — вообще не триггерами, а журналированием на стороне сервера или логикой в приложении.": (
        "A system trigger (ON DATABASE / ON SCHEMA) — an Oracle trigger not on a table but on a database or schema event: LOGON, LOGOFF, SERVERERROR, DDL, STARTUP and so on. ora2pg converts it as an ordinary table trigger, putting the word database/schema where the table name goes: the result is 'CREATE TRIGGER ... AFTER LOGON ON database FOR EACH ROW' (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-052-system-trigger.md). PostgreSQL fails with a syntax error right at the event name. There is no direct equivalent for any of them: DDL events are covered by PostgreSQL event triggers (CREATE EVENT TRIGGER ... ON ddl_command_end), while LOGON/LOGOFF/SERVERERROR are not covered by triggers at all, but by server-side logging or application logic."
    ),
    'FOLLOWS / PRECEDES — оговорка Oracle, задающая порядок срабатывания триггеров на одном и том же событии одной таблицы. ora2pg не просто теряет её: оговорка попадает внутрь тела сгенерированной функции, между \'AS $BODY$\' и \'BEGIN\' (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-053-trigger-follows.md). CREATE FUNCTION и CREATE TRIGGER проходят без ошибок — ora2pg выставляет в своём выводе check_function_bodies = false, — а при первом же INSERT триггер падает с \'syntax error at or near "FOLLOWS"\'. То есть ломается не порядок срабатывания, а вся операция с таблицей. В PostgreSQL порядка «по имени предшественника» нет вообще: триггеры на одном событии срабатывают в алфавитном порядке имён, поэтому оговорку нужно убрать, а нужную последовательность обеспечить именованием (t10_..., t20_...) или слиянием триггеров в один.': (
        'FOLLOWS / PRECEDES — Oracle\'s clause specifying the firing order of triggers on the same event of the same table. ora2pg does not merely lose it: the clause ends up inside the generated function\'s body, between \'AS $BODY$\' and \'BEGIN\' (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-053-trigger-follows.md). CREATE FUNCTION and CREATE TRIGGER both succeed — ora2pg sets check_function_bodies = false in its output — and then the very first INSERT fails with \'syntax error at or near "FOLLOWS"\'. So what breaks is not the firing order but every operation on the table. PostgreSQL has no "after this named trigger" ordering at all: triggers on the same event fire in alphabetical name order, so the clause has to go, with the required sequence enforced through naming (t10_..., t20_...) or by merging the triggers into one.'
    ),
    'TABLE(...) — оператор Oracle, разворачивающий коллекцию (nested table, VARRAY или результат pipelined-функции) в набор строк прямо во FROM. ora2pg копирует его в вывод как есть (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-054-table-collection.md). В PostgreSQL такого оператора нет, и запрос падает синтаксической ошибкой прямо на слове TABLE. Ближайший аналог — unnest(...) для массива или обычный вызов set-returning функции во FROM (FROM get_ids(42)), но подстановка не механическая: она зависит от того, чем в PostgreSQL стала сама коллекция (массивом, отдельной таблицей или функцией, возвращающей SETOF), — см. GAP-021/collection_type.py про сами объявления таких типов.': (
        "TABLE(...) — Oracle's operator that expands a collection (a nested table, a VARRAY, or the result of a pipelined function) into a row set directly in the FROM clause. ora2pg copies it into its output unchanged (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-054-table-collection.md). PostgreSQL has no such operator and the query fails with a syntax error right at the word TABLE. The closest equivalents are unnest(...) for an array or a plain set-returning function call in FROM (FROM get_ids(42)), but the substitution is not mechanical: it depends on what the collection itself became in PostgreSQL (an array, a separate table, or a function returning SETOF) — see GAP-021/collection_type.py about the declarations of those types."
    ),
    'CURSOR(SELECT ...) — курсорное выражение Oracle: вложенный запрос, возвращаемый как отдельный столбец-курсор, который клиент потом открывает и читает построчно. ora2pg копирует конструкцию в вывод как есть (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-055-cursor-expression.md). В PostgreSQL курсорных выражений нет, и запрос падает синтаксической ошибкой на SELECT внутри CURSOR(. Переписывается либо на обычное соединение с агрегацией дочерних строк в массив/json (array_agg, json_agg) — чаще всего именно это и имелось в виду, — либо на отдельную функцию, возвращающую refcursor, если клиент действительно читает вложенный набор построчно.': (
        'CURSOR(SELECT ...) — an Oracle cursor expression: a nested query returned as a separate cursor column that the client then opens and reads row by row. ora2pg copies the construct into its output unchanged (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-055-cursor-expression.md). PostgreSQL has no cursor expressions, and the query fails with a syntax error at the SELECT inside CURSOR(. It is rewritten either as an ordinary join with the child rows aggregated into an array or json (array_agg, json_agg) — which is most often what was actually meant — or as a separate function returning a refcursor, if the client really does read the nested set row by row.'
    ),
    "FOR UPDATE ... WAIT n — блокировка строк с ожиданием не дольше n секунд. ora2pg копирует оговорку в вывод как есть (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-056-for-update-wait.md). У PostgreSQL для FOR UPDATE есть только NOWAIT и SKIP LOCKED — варианта «подожди ровно n секунд» нет, — поэтому запрос падает синтаксической ошибкой на слове WAIT. Эквивалент делается на уровне сессии, а не запроса: SET LOCAL lock_timeout = 'n s' перед SELECT ... FOR UPDATE. Разница не только в синтаксисе: по истечении времени Oracle возвращает ORA-30006, а PostgreSQL прерывает запрос по lock_timeout, так что обработку ошибки в вызывающем коде тоже нужно поправить.": (
        'FOR UPDATE ... WAIT n — row locking that waits no longer than n seconds. ora2pg copies the clause into its output unchanged (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-056-for-update-wait.md). PostgreSQL\'s FOR UPDATE offers only NOWAIT and SKIP LOCKED — there is no "wait exactly n seconds" variant — so the query fails with a syntax error at the word WAIT. The equivalent is set at session level rather than per query: SET LOCAL lock_timeout = \'n s\' before SELECT ... FOR UPDATE. The difference is not only syntactic: on expiry Oracle returns ORA-30006 while PostgreSQL aborts the query on lock_timeout, so the error handling in the calling code needs adjusting too.'
    ),
    "ROWNUM в UPDATE/DELETE — ограничение числа изменяемых строк по-Oracle'овски. ora2pg переписывает 'WHERE ROWNUM <= n' в 'LIMIT n' (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-057-rownum-dml.md). Для SELECT это верная замена, но у UPDATE и DELETE в PostgreSQL оговорки LIMIT нет вообще — сгенерированный 'UPDATE ... LIMIT 10' падает синтаксической ошибкой на слове LIMIT. Переписывается через подзапрос по первичному ключу: DELETE FROM t WHERE id IN (SELECT id FROM t WHERE ... LIMIT n). Важно, что смысл при этом всё равно меняется: Oracle не обещает, какие именно n строк попадут под ROWNUM, поэтому во внутренний SELECT почти всегда нужно дописать явный ORDER BY, иначе выбор строк останется недетерминированным.": (
        "ROWNUM in an UPDATE/DELETE — the Oracle way of limiting how many rows are changed. ora2pg rewrites 'WHERE ROWNUM <= n' into 'LIMIT n' (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-057-rownum-dml.md). For a SELECT that is the right substitution, but PostgreSQL's UPDATE and DELETE have no LIMIT clause at all — the generated 'UPDATE ... LIMIT 10' fails with a syntax error at the word LIMIT. It is rewritten through a primary-key subquery: DELETE FROM t WHERE id IN (SELECT id FROM t WHERE ... LIMIT n). Note that the meaning changes either way: Oracle makes no promise about which n rows ROWNUM picks, so the inner SELECT almost always needs an explicit ORDER BY added, otherwise the choice of rows stays non-deterministic."
    ),
    "TO_DATE/TO_TIMESTAMP с форматом RR — Oracle-специфичный код двузначного года с «поворотным» правилом: 00-49 читается как 20xx, 50-99 как 19xx. ora2pg оставляет RR в строке формата как есть (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-058-to-date-rr.md). PostgreSQL такого кода формата не знает и, что хуже всего, не ругается на него: to_date('85-06-01','RR-MM-DD') молча возвращает 0001-06-01 BC — первый год до нашей эры вместо 1985 года. Ошибки нет ни на загрузке, ни на выполнении, данные просто оказываются неверными. Заменять нужно на явный четырёхзначный YYYY с приведением входных данных: YY тут не эквивалент, хотя выглядит им. Пороги у правил разные — у Oracle RR это 00-49 → 20xx, 50-99 → 19xx, а у PostgreSQL YY это 00-69 → 20xx, 70-99 → 19xx (проверено на PostgreSQL 16). Совпадают они только на 00-49 и 70-99, а на 50-69 расходятся ровно на сто лет: '65' по Oracle это 1965 год, а по YY в PostgreSQL — 2065. Отдельно стоит отметить асимметрию в самом ora2pg: в TO_CHAR он RR на YY заменяет, а в TO_DATE — нет.": (
        "TO_DATE/TO_TIMESTAMP with an RR format — Oracle's own two-digit year code with a pivot rule: 00-49 reads as 20xx, 50-99 as 19xx. ora2pg leaves RR in the format string as it is (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-058-to-date-rr.md). PostgreSQL does not know that format code and, worst of all, does not complain about it: to_date('85-06-01','RR-MM-DD') silently returns 0001-06-01 BC — year one before Christ instead of 1985. There is no error at load time or at run time, the data is simply wrong. Replace it with an explicit four-digit YYYY after normalising the input: YY is not an equivalent here, though it looks like one. The two rules pivot at different points — Oracle's RR is 00-49 → 20xx, 50-99 → 19xx, while PostgreSQL's YY is 00-69 → 20xx, 70-99 → 19xx (verified on PostgreSQL 16). They agree on 00-49 and 70-99 and disagree by exactly a century on 50-69: '65' is 1965 under Oracle's RR and 2065 under PostgreSQL's YY. Worth noting separately is an asymmetry inside ora2pg itself: in TO_CHAR it does replace RR with YY, in TO_DATE it does not."
    ),
    "AUTHID CURRENT_USER / AUTHID DEFINER — оговорка прав выполнения у процедуры, функции или пакета. Из всех gap'ов этого реестра последствие здесь самое неприятное: ora2pg не конвертирует объект с такой оговоркой, а молча выбрасывает его целиком — в выводе остаётся только '-- Nothing found of type PROCEDURE', и даже строки уровня DEBUG в логе не появляется (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16 с контрольным замером: та же процедура без AUTHID конвертируется штатно, docs/research/gap-059-authid-clause.md). Ошибки не будет ни на конвертации, ни на загрузке — процедуры просто не окажется в целевой базе, и обнаружится это при первом вызове из приложения. В PostgreSQL прямые аналоги есть: AUTHID DEFINER — это SECURITY DEFINER, AUTHID CURRENT_USER — это SECURITY INVOKER (поведение по умолчанию), так что оговорку нужно убрать из исходника перед конвертацией и дописать нужный вариант в готовую функцию.": (
        "AUTHID CURRENT_USER / AUTHID DEFINER — the execution-rights clause on a procedure, function or package. Of every gap in this registry the consequence here is the nastiest: ora2pg does not convert an object carrying this clause, it silently drops the object entirely — all that is left in the output is '-- Nothing found of type PROCEDURE', and not even a DEBUG-level line appears in the log (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run with a control case: the same procedure without AUTHID converts normally, docs/research/gap-059-authid-clause.md). No error is raised at conversion or at load time — the procedure simply is not in the target database, and that gets discovered on the first call from the application. PostgreSQL does have direct equivalents: AUTHID DEFINER is SECURITY DEFINER, AUTHID CURRENT_USER is SECURITY INVOKER (the default), so the clause has to be removed from the source before converting and the right variant added to the finished function."
    ),
    "PRAGMA EXCEPTION_INIT — привязка объявленного исключения к номеру ошибки Oracle, чтобы ловить её по имени в WHEN. ora2pg выбрасывает сам PRAGMA и переписывает обработчик в WHEN SQLSTATE '50001' — причём в одну и ту же константу '50001' независимо от того, какой номер ORA стоял в PRAGMA (проверено на -1 и на -60, подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-060-pragma-exception-init.md). Процедура создаётся без единой ошибки, а обработчик становится мёртвым кодом: PostgreSQL такой SQLSTATE не возбуждает никогда, у него свои коды (нарушение уникальности — 23505, взаимоблокировка — 40P01). На практике это значит, что обработанная в Oracle ошибка после миграции молча вылетает наружу и роняет вызывающий код. Каждый номер ORA нужно вручную сопоставить с настоящим кодом PostgreSQL и заменить '50001' на него (или на именованное условие вроде unique_violation).": (
        "PRAGMA EXCEPTION_INIT — binding a declared exception to an Oracle error number so it can be caught by name in WHEN. ora2pg drops the pragma itself and rewrites the handler as WHEN SQLSTATE '50001' — and into that same constant '50001' regardless of which ORA number the pragma carried (checked with -1 and with -60, confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-060-pragma-exception-init.md). The procedure is created without a single error and the handler becomes dead code: PostgreSQL never raises that SQLSTATE, it has its own codes (unique violation is 23505, deadlock is 40P01). In practice this means an error that Oracle handled now silently escapes after the migration and takes the calling code down with it. Each ORA number has to be mapped by hand onto the real PostgreSQL code and '50001' replaced with it (or with a named condition such as unique_violation)."
    ),
    "SUBTYPE ... RANGE lo .. hi — подтип PL/SQL с ограничением диапазона значений. ora2pg переводит объявление в CREATE DOMAIN, но оговорку RANGE переносит в него дословно: получается 'CREATE DOMAIN pkg.small_int AS integer RANGE 1 .. 100' (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-061-subtype-range.md). У CREATE DOMAIN в PostgreSQL такой оговорки нет, и DDL падает синтаксической ошибкой на слове RANGE. Идея переносится один в один, но другим синтаксисом — через проверку: CREATE DOMAIN small_int AS integer CHECK (VALUE BETWEEN 1 AND 100). Ненагруженные подтипы (SUBTYPE s IS PLS_INTEGER; и вариант с NOT NULL) ora2pg конвертирует корректно, и этот детектор их не помечает.": (
        "SUBTYPE ... RANGE lo .. hi — a PL/SQL subtype with a value-range constraint. ora2pg translates the declaration into CREATE DOMAIN but carries the RANGE clause across verbatim, producing 'CREATE DOMAIN pkg.small_int AS integer RANGE 1 .. 100' (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-061-subtype-range.md). PostgreSQL's CREATE DOMAIN has no such clause and the DDL fails with a syntax error at the word RANGE. The idea carries over exactly, just in different syntax — as a check: CREATE DOMAIN small_int AS integer CHECK (VALUE BETWEEN 1 AND 100). Unconstrained subtypes (SUBTYPE s IS PLS_INTEGER; and the NOT NULL variant) are converted correctly by ora2pg, and this detector does not flag them."
    ),
    "q'[...]' — альтернативные кавычки Oracle: способ записать строку с апострофами внутри, не удваивая их. ora2pg копирует такой литерал в вывод как есть (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-062-alt-quote-literal.md). PostgreSQL этот синтаксис не понимает: q воспринимается как отдельный идентификатор, а дальше начинается обычный строковый литерал, и разбор уезжает — в PL/pgSQL-теле это 'mismatched parentheses' при первом вызове (загрузка проходит чисто, потому что ora2pg выставляет check_function_bodies = false). Заменяется на обычный литерал с удвоенными апострофами или, что ближе по духу, на долларовые кавычки PostgreSQL: $q$it's a test$q$ — внутри них экранировать не нужно ничего.": (
        "q'[...]' — Oracle's alternative quoting: a way to write a string containing apostrophes without doubling them. ora2pg copies such a literal into its output unchanged (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-062-alt-quote-literal.md). PostgreSQL does not understand this syntax: q is read as a separate identifier and an ordinary string literal starts after it, so parsing goes off the rails — inside a PL/pgSQL body that shows up as 'mismatched parentheses' on the first call (loading succeeds cleanly, because ora2pg sets check_function_bodies = false). Replace it with an ordinary literal using doubled apostrophes or, closer in spirit, with PostgreSQL dollar quoting: $q$it's a test$q$ — nothing inside needs escaping there."
    ),
    'GOTO — безусловный переход на метку <<label>> внутри PL/SQL-блока. ora2pg копирует и метку, и сам GOTO в вывод как есть (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-063-goto-statement.md). В PL/pgSQL оператора GOTO нет вообще. CREATE PROCEDURE при этом проходит без ошибок — ora2pg выставляет в своём выводе check_function_bodies = false, поэтому тело не разбирается на загрузке, — и падение происходит при первом же реальном вызове. Переписывается на управляющие конструкции: переход назад — на LOOP/CONTINUE, переход вперёд через кусок кода — на IF/ELSE или на выделение этого куска во вложенный блок с EXIT.': (
        'GOTO — an unconditional jump to a <<label>> inside a PL/SQL block. ora2pg copies both the label and the GOTO itself into its output unchanged (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-063-goto-statement.md). PL/pgSQL has no GOTO statement at all. CREATE PROCEDURE nevertheless succeeds without errors — ora2pg sets check_function_bodies = false in its output, so the body is not parsed at load time — and the failure happens on the very first real call. It is rewritten with control structures: a backward jump becomes LOOP/CONTINUE, a forward jump over a chunk of code becomes IF/ELSE or that chunk extracted into a nested block with EXIT.'
    ),
    '<курсор>%ROWTYPE — объявление переменной по структуре курсора. ora2pg копирует конструкцию в вывод как есть (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-064-cursor-rowtype.md). PL/pgSQL понимает %ROWTYPE только от таблицы или представления, но не от курсора, поэтому имя курсора трактуется как имя отношения и при первом же вызове процедура падает с \'relation "c" does not exist\'. Сама загрузка проходит чисто: ora2pg выставляет в своём выводе check_function_bodies = false, так что тело не разбирается на CREATE PROCEDURE. Заменяется на RECORD — в PL/pgSQL переменная типа RECORD принимает строку любого курсора, и FETCH в неё работает без изменений. Обратите внимание: обычное <таблица>%ROWTYPE ora2pg переносит корректно, и этот детектор его не помечает — только %ROWTYPE от курсора, объявленного в том же файле.': (
        '<cursor>%ROWTYPE — declaring a variable after the shape of a cursor. ora2pg copies the construct into its output unchanged (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-064-cursor-rowtype.md). PL/pgSQL understands %ROWTYPE only against a table or a view, never a cursor, so the cursor name is read as a relation name and on the very first call the procedure fails with \'relation "c" does not exist\'. Loading itself is clean: ora2pg sets check_function_bodies = false in its output, so the body is not parsed at CREATE PROCEDURE. Replace it with RECORD — in PL/pgSQL a RECORD variable accepts a row from any cursor and FETCH into it works unchanged. Note that ordinary <table>%ROWTYPE is carried over correctly by ora2pg and this detector does not flag it — only %ROWTYPE against a cursor declared in the same file.'
    ),
    "WM_CONCAT — недокументированная агрегатная функция Oracle, склеивающая значения группы в одну строку через запятую. Она никогда не поддерживалась официально и убрана начиная с 12c, но в унаследованном коде встречается постоянно. ora2pg копирует вызов в вывод как есть (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-065-wm-concat.md) — в отличие от LISTAGG, который он переписывает в string_agg. В PostgreSQL такой функции нет, и запрос падает с 'function wm_concat(text) does not exist'. Заменяется на string_agg(col, ','), и при замене стоит сразу дописать порядок — string_agg(col, ',' ORDER BY col): WM_CONCAT порядок никак не гарантировал, поэтому «как было» воспроизвести всё равно нельзя, а молча недетерминированный результат лучше сделать явным.": (
        'WM_CONCAT — an undocumented Oracle aggregate that glues a group\'s values into a single comma-separated string. It was never officially supported and was removed as of 12c, but it turns up constantly in legacy code. ora2pg copies the call into its output unchanged (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-065-wm-concat.md) — unlike LISTAGG, which it does rewrite into string_agg. PostgreSQL has no such function and the query fails with \'function wm_concat(text) does not exist\'. Replace it with string_agg(col, \',\'), and while replacing it is worth adding the ordering straight away — string_agg(col, \',\' ORDER BY col): WM_CONCAT guaranteed no ordering at all, so "as it was" cannot be reproduced anyway, and a silently non-deterministic result is better made explicit.'
    ),
    'CREATE VIEW ... WITH READ ONLY — представление, через которое Oracle запрещает менять данные: INSERT/UPDATE/DELETE по нему падают с ORA-42399. ora2pg просто выбрасывает оговорку из вывода (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-066-read-only-view.md). Ошибки не будет ни на загрузке, ни потом: простое представление в PostgreSQL по умолчанию автоматически обновляемое, поэтому INSERT через него молча проходит и пишет строку в базовую таблицу — проверено, строка действительно появляется. Защита, которая в Oracle была объявлена в самом определении объекта, после миграции исчезает бесследно. Восстанавливается либо правами (REVOKE INSERT, UPDATE, DELETE ON <view> FROM ...), либо триггером INSTEAD OF, возбуждающим исключение. Родственный gap про таблицы — GAP-026/read_only_table.py.': (
        "CREATE VIEW ... WITH READ ONLY — a view through which Oracle forbids changing data: INSERT/UPDATE/DELETE against it fail with ORA-42399. ora2pg simply drops the clause from its output (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-066-read-only-view.md). No error appears at load time or later: a simple view in PostgreSQL is automatically updatable by default, so an INSERT through it silently succeeds and writes a row into the base table — verified, the row really does appear. Protection that in Oracle was declared in the object's own definition vanishes without trace after the migration. It is restored either with privileges (REVOKE INSERT, UPDATE, DELETE ON <view> FROM ...) or with an INSTEAD OF trigger that raises an exception. The related gap for tables is GAP-026/read_only_table.py."
    ),
    'SDO_GEOMETRY — пространственный тип Oracle Spatial. ora2pg конвертирует его в geometry(GEOMETRY) — то есть в тип расширения PostGIS, — но саму строку CREATE EXTENSION postgis в вывод не добавляет (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-067-sdo-geometry.md). На чистой PostgreSQL без предварительно установленного PostGIS DDL падает на загрузке с \'type "geometry" does not exist\'. Само по себе отображение выбрано верно, поэтому severity здесь medium, а не high: чинится это одной строкой CREATE EXTENSION postgis перед загрузкой схемы. Заметить стоит другое — в том же прогоне для SYS_GUID() ora2pg строку CREATE EXTENSION "uuid-ossp" выводит сам, так что рассчитывать на автоматическое подключение нужного расширения нельзя. Отдельно проверьте перенос самих значений: модель координат и семантика SDO_GEOMETRY и PostGIS совпадают не полностью.': (
        'SDO_GEOMETRY — the Oracle Spatial geometry type. ora2pg converts it into geometry(GEOMETRY) — that is, into a PostGIS extension type — but does not add the CREATE EXTENSION postgis line itself to the output (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-067-sdo-geometry.md). On a clean PostgreSQL without PostGIS installed beforehand, the DDL fails at load time with \'type "geometry" does not exist\'. The mapping itself is the right choice, which is why the severity here is medium rather than high: it is fixed by one CREATE EXTENSION postgis line before loading the schema. What is worth noticing is something else — in the same run ora2pg does emit CREATE EXTENSION "uuid-ossp" by itself for SYS_GUID(), so the needed extension being wired up automatically is not something to count on. Check the migration of the values themselves separately as well: the coordinate model and semantics of SDO_GEOMETRY and PostGIS do not fully coincide.'
    ),
    'ENUM(...) — столбец с перечислимым типом MySQL/MariaDB. ora2pg (-m) синтезирует под него именованный PostgreSQL-тип <таблица>_<столбец>_t и подставляет это имя в определение столбца, но сам оператор CREATE TYPE ... AS ENUM (...), которым этот тип должен быть объявлен, в вывод не попадает — подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16 (docs/research/gap-068-mysql-enum-type.md). CREATE TABLE падает немедленно, при загрузке схемы: \'type "<таблица>_<столбец>_t" does not exist\'. Значения перечисления при этом никуда не теряются — они видны прямо в исходном ENUM(...), — так что руками нужно лишь вставить недостающий CREATE TYPE перед CREATE TABLE.': (
        'ENUM(...) -- a MySQL/MariaDB enumerated-type column. ora2pg (-m) synthesizes a named PostgreSQL type <table>_<column>_t for it and substitutes that name into the column definition, but the CREATE TYPE ... AS ENUM (...) statement that type itself needs never makes it into the output (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-068-mysql-enum-type.md). CREATE TABLE fails immediately, at schema load time: \'type "<table>_<column>_t" does not exist\'. The enum values themselves are never lost -- they are right there in the source ENUM(...) -- so all that\'s needed by hand is inserting the missing CREATE TYPE before CREATE TABLE.'
    ),
    'DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP — MySQL/MariaDB-специфичное авто-обновление столбца на каждый UPDATE строки, часть самого DEFAULT. ora2pg (-m) копирует \'ON UPDATE CURRENT_TIMESTAMP\' в вывод дословно, прямо внутри DEFAULT — подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16 (docs/research/gap-069-mysql-on-update-current-timestamp.md). В PostgreSQL у DEFAULT нет такого синтаксиса вообще, и CREATE TABLE падает немедленно, при загрузке схемы: \'syntax error at or near "ON"\'. Переносится на триггер BEFORE UPDATE, выставляющий NEW.<столбец> = now() (или на GENERATED ALWAYS, если версия PostgreSQL это позволяет для конкретного случая).': (
        'DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP -- MySQL/MariaDB\'s own auto-update-on-every-UPDATE clause, part of DEFAULT itself. ora2pg (-m) copies \'ON UPDATE CURRENT_TIMESTAMP\' into the output verbatim, right inside DEFAULT (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-069-mysql-on-update-current-timestamp.md). PostgreSQL\'s DEFAULT has no such syntax at all, and CREATE TABLE fails immediately, at schema load time: \'syntax error at or near "ON"\'. Move it to a BEFORE UPDATE trigger that sets NEW.<column> = now() (or to GENERATED ALWAYS, if the PostgreSQL version in use allows it for this specific case).'
    ),
    'INSERT ... ON DUPLICATE KEY UPDATE — MySQL/MariaDB-специфичный upsert: обновить существующую строку, если вставка конфликтует с уникальным ключом/PRIMARY KEY, иначе вставить новую. ora2pg (-m) копирует весь оператор ON DUPLICATE KEY UPDATE в тело процедуры/функции дословно, без какого-либо преобразования — подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16 (docs/research/gap-070-mysql-on-duplicate-key-update.md). Такого синтаксиса у INSERT в PostgreSQL нет вообще. CREATE PROCEDURE/FUNCTION при этом проходит без ошибок — ora2pg выставляет в своём выводе check_function_bodies = false, поэтому тело не разбирается на загрузке, — и падение происходит при первом же реальном вызове: \'syntax error at or near "DUPLICATE"\'. Переписывается на INSERT ... ON CONFLICT (<уникальный_ключ>) DO UPDATE SET ....': (
        'INSERT ... ON DUPLICATE KEY UPDATE -- MySQL/MariaDB\'s own upsert: update the existing row if the insert conflicts with a unique key/PRIMARY KEY, otherwise insert a new one. ora2pg (-m) copies the whole ON DUPLICATE KEY UPDATE clause into the procedure/function body verbatim, with no rewriting at all (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-070-mysql-on-duplicate-key-update.md). PostgreSQL\'s INSERT has no such syntax at all. CREATE PROCEDURE/FUNCTION nevertheless succeeds without errors -- ora2pg sets check_function_bodies = false in its output, so the body is not parsed at load time -- and the failure happens on the very first real call: \'syntax error at or near "DUPLICATE"\'. Rewrite it as INSERT ... ON CONFLICT (<unique key>) DO UPDATE SET ....'
    ),
    'SIGNAL/RESIGNAL — MySQL/MariaDB-специфичные операторы возбуждения и повторного возбуждения условия (аналог RAISE в PL/pgSQL). ora2pg (-m) копирует SIGNAL/RESIGNAL в тело процедуры/функции дословно (теряя по пути ключевое слово SET перед MESSAGE_TEXT) — подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16 (docs/research/gap-071-mysql-signal.md). Ни SIGNAL, ни RESIGNAL в PL/pgSQL не существуют вообще. CREATE PROCEDURE/FUNCTION при этом проходит без ошибок — ora2pg выставляет в своём выводе check_function_bodies = false, поэтому тело не разбирается на загрузке, — и падение происходит при первом же реальном вызове: \'syntax error at or near "SIGNAL"\' (или "RESIGNAL"). Переписывается на RAISE EXCEPTION ... USING ERRCODE = \'<sqlstate>\', MESSAGE = \'<текст>\'.': (
        'SIGNAL/RESIGNAL -- MySQL/MariaDB\'s own statements for raising and re-raising a condition (the counterpart of RAISE in PL/pgSQL). ora2pg (-m) copies SIGNAL/RESIGNAL into the procedure/function body verbatim (losing the SET keyword before MESSAGE_TEXT along the way) -- confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-071-mysql-signal.md. Neither SIGNAL nor RESIGNAL exists in PL/pgSQL at all. CREATE PROCEDURE/FUNCTION nevertheless succeeds without errors -- ora2pg sets check_function_bodies = false in its output, so the body is not parsed at load time -- and the failure happens on the very first real call: \'syntax error at or near "SIGNAL"\' (or "RESIGNAL"). Rewrite it as RAISE EXCEPTION ... USING ERRCODE = \'<sqlstate>\', MESSAGE = \'<text>\'.'
    ),
    'FULLTEXT KEY/INDEX — полнотекстовый индекс MySQL/MariaDB, объявленный прямо в списке столбцов CREATE TABLE. ora2pg (-m) не распознаёт эту конструкцию как индекс: имя индекса и список столбцов теряются, а сами слова \'FULLTEXT KEY\'/\'FULLTEXT INDEX\' остаются в выводе на месте, где ожидалось очередное определение столбца — подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16 (docs/research/gap-072-mysql-fulltext-index.md). CREATE TABLE падает немедленно, при загрузке схемы: \'type "key" does not exist\' (PostgreSQL читает \'fulltext\' как имя нового столбца, а \'KEY\'/\'INDEX\' — как имя несуществующего типа для него). Восстанавливается вручную: столбцы полнотекстового индекса видны в исходном FULLTEXT KEY (...), переносятся на CREATE INDEX ... USING gin (to_tsvector(\'...\', ...)) после CREATE TABLE.': (
        'FULLTEXT KEY/INDEX -- a MySQL/MariaDB full-text index declared right inside CREATE TABLE\'s column list. ora2pg (-m) doesn\'t recognize this construct as an index at all: the index name and its column list are lost, and the bare words \'FULLTEXT KEY\'/\'FULLTEXT INDEX\' are left sitting in the output where the next column definition was expected (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-072-mysql-fulltext-index.md). CREATE TABLE fails immediately, at schema load time: \'type "key" does not exist\' (PostgreSQL reads \'fulltext\' as the name of a new column and \'KEY\'/\'INDEX\' as the name of a type for it that doesn\'t exist). Rebuild it by hand: the full-text index\'s columns are visible in the source FULLTEXT KEY (...), moved onto a CREATE INDEX ... USING gin (to_tsvector(\'...\', ...)) after CREATE TABLE.'
    ),
    'KEY <имя> (<столбцы>) — обычный (не уникальный) индекс, объявленный в списке столбцов CREATE TABLE. Это ровно то написание, которое по умолчанию выдаёт mysqldump, и именно оно ломается: ora2pg (-m) не распознаёт его как индекс — имя индекса и список столбцов теряются, а в выводе на месте очередного определения столбца остаётся обрубок \'key <ИМЯ_ИНДЕКСА>\' (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-073-mysql-key-index.md). CREATE TABLE падает немедленно, при загрузке схемы: \'type "<имя_индекса>" does not exist\' — PostgreSQL читает \'key\' как имя нового столбца, а имя индекса как имя несуществующего типа для него. Безымянная форма KEY (<столбцы>) не ломает загрузку, но пропадает из вывода целиком, молча. Обратите внимание: синоним INDEX <имя> (<столбцы>) — та же самая конструкция MySQL — конвертируется корректно, в CREATE INDEX, и этим детектором не помечается; UNIQUE KEY тоже переносится (теряется только имя ограничения). Чинится переписыванием в CREATE INDEX <имя> ON <таблица> (<столбцы>) после CREATE TABLE.': (
        'KEY <name> (<columns>) -- an ordinary (non-unique) index declared in a CREATE TABLE column list. This is exactly the spelling mysqldump emits by default, and it is exactly the one that breaks: ora2pg (-m) doesn\'t recognize it as an index -- the index name and column list are lost, and a \'key <INDEX_NAME>\' stub is left in the output where the next column definition was expected (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-073-mysql-key-index.md). CREATE TABLE fails immediately, at schema load time: \'type "<index_name>" does not exist\' -- PostgreSQL reads \'key\' as the name of a new column and the index name as a type for it that doesn\'t exist. The unnamed form KEY (<columns>) doesn\'t break the load, but disappears from the output entirely, silently. Note that the synonym INDEX <name> (<columns>) -- the very same MySQL construct -- converts correctly into CREATE INDEX and is deliberately not flagged here; UNIQUE KEY is carried over too (only the constraint name is lost). The fix is to rewrite it as CREATE INDEX <name> ON <table> (<columns>) after CREATE TABLE.'
    ),
    'SPATIAL KEY/INDEX — пространственный индекс MySQL/MariaDB, объявленный в списке столбцов CREATE TABLE. ora2pg (-m) не распознаёт конструкцию как индекс: имя индекса и список столбцов теряются, а слова \'spatial KEY\' остаются в выводе на месте, где ожидалось очередное определение столбца — подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16 (docs/research/gap-074-mysql-spatial-index.md). CREATE TABLE падает немедленно, при загрузке схемы: \'type "key" does not exist\'. Отличается от родственного GAP-072 (FULLTEXT) не только ключевым словом, но и починкой: пространственный индекс восстанавливается как CREATE INDEX ... USING gist (<столбец>) поверх PostGIS-типа, и отдельно нужно проверить сам тип столбца — MySQL-овские POINT/GEOMETRY переносятся не всегда так, как ожидается.': (
        'SPATIAL KEY/INDEX -- a MySQL/MariaDB spatial index declared in a CREATE TABLE column list. ora2pg (-m) doesn\'t recognize the construct as an index: the index name and column list are lost, and the words \'spatial KEY\' are left in the output where the next column definition was expected (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-074-mysql-spatial-index.md). CREATE TABLE fails immediately, at schema load time: \'type "key" does not exist\'. It differs from the related GAP-072 (FULLTEXT) in more than the keyword: the fix differs too -- a spatial index is rebuilt as CREATE INDEX ... USING gist (<column>) over a PostGIS type, and the column type itself needs checking separately, since MySQL\'s POINT/GEOMETRY don\'t always carry over the way one expects.'
    ),
    "LIMIT <смещение>, <количество> — MySQL/MariaDB-специфичная форма постраничной выборки через запятую. ora2pg (-m) копирует её в тело процедуры/функции дословно (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-075-mysql-limit-comma.md). PostgreSQL такую запись не принимает и сообщает об этом прямо: 'LIMIT #,# syntax is not supported'. CREATE PROCEDURE/FUNCTION при этом проходит без ошибок — ora2pg выставляет в своём выводе check_function_bodies = false, поэтому тело не разбирается на загрузке, — и падение происходит при первом же реальном вызове. Переписывается на LIMIT <количество> OFFSET <смещение>. Обратите внимание на порядок: в MySQL-форме первым идёт смещение, поэтому механическая замена запятой на OFFSET без перестановки аргументов даст молча другую страницу выдачи.": (
        "LIMIT <offset>, <count> -- MySQL/MariaDB's own comma form of pagination. ora2pg (-m) copies it into the procedure/function body verbatim (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-075-mysql-limit-comma.md). PostgreSQL does not accept this spelling and says so plainly: 'LIMIT #,# syntax is not supported'. CREATE PROCEDURE/FUNCTION nevertheless succeeds without errors -- ora2pg sets check_function_bodies = false in its output, so the body is not parsed at load time -- and the failure happens on the very first real call. Rewrite it as LIMIT <count> OFFSET <offset>. Mind the order: the MySQL form puts the offset first, so mechanically swapping the comma for OFFSET without reordering the arguments silently returns a different page."
    ),
    'REPLACE INTO — MySQL/MariaDB-специфичный оператор: вставить строку, а если строка с таким же уникальным ключом уже есть — удалить её и вставить новую. ora2pg (-m) копирует оператор в тело процедуры/функции дословно (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-076-mysql-replace-into.md). Такого оператора в PostgreSQL нет. CREATE PROCEDURE/FUNCTION проходит без ошибок — ora2pg выставляет в своём выводе check_function_bodies = false, поэтому тело не разбирается на загрузке, — и падение происходит при первом же реальном вызове. Переписывается на INSERT ... ON CONFLICT (<ключ>) DO UPDATE SET ..., но перевод не дословный, и разницу стоит держать в голове: REPLACE именно удаляет старую строку и вставляет новую, поэтому по ней срабатывают ON DELETE-триггеры и каскадные удаления дочерних строк, а не перечисленные в запросе столбцы получают значения по умолчанию, а не сохраняют прежние. ON CONFLICT DO UPDATE ведёт себя ровно наоборот, так что на таблице с внешними ключами ON DELETE CASCADE механическая замена изменит поведение.': (
        'REPLACE INTO -- a MySQL/MariaDB-specific statement: insert a row, and if a row with the same unique key already exists, delete it and insert the new one. ora2pg (-m) copies the statement into the procedure/function body verbatim (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-076-mysql-replace-into.md). PostgreSQL has no such statement. CREATE PROCEDURE/FUNCTION succeeds without errors -- ora2pg sets check_function_bodies = false in its output, so the body is not parsed at load time -- and the failure happens on the very first real call. Rewrite it as INSERT ... ON CONFLICT (<key>) DO UPDATE SET ..., but the translation is not literal and the difference is worth keeping in mind: REPLACE really does delete the old row and insert a new one, so ON DELETE triggers and cascading deletes of child rows fire, and columns not listed in the statement get their defaults rather than keeping their previous values. ON CONFLICT DO UPDATE behaves exactly the other way round, so on a table with ON DELETE CASCADE foreign keys a mechanical swap changes behavior.'
    ),
    'INSERT IGNORE — MySQL/MariaDB-специфичная форма вставки, которая превращает ошибки в предупреждения и молча пропускает проблемные строки. ora2pg (-m) копирует оператор в тело процедуры/функции дословно (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-077-mysql-insert-ignore.md). Такого синтаксиса у INSERT в PostgreSQL нет. CREATE PROCEDURE/FUNCTION проходит без ошибок — ora2pg выставляет в своём выводе check_function_bodies = false, поэтому тело не разбирается на загрузке, — и падение происходит при первом же реальном вызове. Ближайший аналог — INSERT ... ON CONFLICT DO NOTHING, но он уже по охвату: IGNORE в MySQL глушит не только конфликт уникальности, но и другие ошибки вставки, вплоть до обрезания слишком длинных значений и подстановки нулей вместо некорректных дат. Если код полагался именно на это широкое поведение, дословный перевод изменит смысл — стоит разобраться, какие именно ошибки там глушились.': (
        "INSERT IGNORE -- MySQL/MariaDB's own form of insert, which turns errors into warnings and silently skips the offending rows. ora2pg (-m) copies the statement into the procedure/function body verbatim (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-077-mysql-insert-ignore.md). PostgreSQL's INSERT has no such syntax. CREATE PROCEDURE/FUNCTION succeeds without errors -- ora2pg sets check_function_bodies = false in its output, so the body is not parsed at load time -- and the failure happens on the very first real call. The closest equivalent is INSERT ... ON CONFLICT DO NOTHING, but it is narrower than IGNORE: in MySQL, IGNORE suppresses more than a uniqueness conflict -- other insert errors too, down to truncating over-long values and substituting zeroes for invalid dates. If the code relied on that broader behavior, a literal translation changes its meaning, and it's worth working out which errors were actually being swallowed."
    ),
    'PREPARE <имя> FROM <строка> — подготовка динамического SQL в хранимой процедуре MySQL/MariaDB (обычно в связке с EXECUTE и DEALLOCATE PREPARE). ora2pg (-m) копирует конструкцию в тело процедуры дословно, лишь заменяя пользовательскую переменную @s на обычную (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-078-mysql-prepare-from.md). Оператор PREPARE в PostgreSQL тоже есть, но синтаксис у него другой — PREPARE <имя> AS <запрос>, — и запрос задаётся текстом самого SQL, а не строковой переменной. Поэтому падение конкретное и узнаваемое: \'syntax error at or near "FROM"\'. Загрузка проходит чисто (ora2pg выставляет в своём выводе check_function_bodies = false), ошибка вылезает при первом вызове. Переписывается не на PostgreSQL-овский PREPARE, а на EXECUTE <строка> внутри PL/pgSQL — это штатный способ выполнить собранный в переменной SQL; параметры передаются через USING, и это же снимает риск SQL-инъекции при склейке строки.': (
        'PREPARE <name> FROM <string> -- preparing dynamic SQL inside a MySQL/MariaDB stored procedure (usually together with EXECUTE and DEALLOCATE PREPARE). ora2pg (-m) copies the construct into the procedure body verbatim, merely replacing the user variable @s with an ordinary one (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-078-mysql-prepare-from.md). PostgreSQL does have a PREPARE statement, but with different syntax -- PREPARE <name> AS <query> -- and the query is given as SQL text, not as a string variable. Hence a specific, recognisable failure: \'syntax error at or near "FROM"\'. Loading is clean (ora2pg sets check_function_bodies = false in its output); the error surfaces on the first call. The rewrite target is not PostgreSQL\'s PREPARE but PL/pgSQL\'s EXECUTE <string> -- the standard way to run SQL assembled in a variable; parameters go through USING, which also removes the SQL-injection risk of string concatenation.'
    ),
    "LAST_INSERT_ID() — функция MySQL/MariaDB, возвращающая значение AUTO_INCREMENT, выданное последней вставкой в текущем соединении. ora2pg (-m) копирует вызов в тело процедуры/функции дословно (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-079-mysql-last-insert-id.md). В PostgreSQL такой функции нет, и при первом же реальном вызове процедура падает с 'function last_insert_id() does not exist'; загрузка при этом проходит чисто, потому что ora2pg выставляет в своём выводе check_function_bodies = false. Переписывается лучше всего на INSERT ... RETURNING <столбец> INTO <переменная> — так значение берётся прямо из выполненной вставки, без обращения к состоянию сессии. Варианты currval('<последовательность>') и lastval() тоже работают, но у lastval() своя тонкость: он относится к последней использованной последовательности вообще, а не к конкретной таблице, поэтому в процедуре, вставляющей в несколько таблиц, легко получить чужое значение.": (
        "LAST_INSERT_ID() -- a MySQL/MariaDB function returning the AUTO_INCREMENT value produced by the last insert on the current connection. ora2pg (-m) copies the call into the procedure/function body verbatim (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-079-mysql-last-insert-id.md). PostgreSQL has no such function, and on the very first real call the routine fails with 'function last_insert_id() does not exist'; loading itself is clean, because ora2pg sets check_function_bodies = false in its output. The best rewrite is INSERT ... RETURNING <column> INTO <variable> -- that takes the value straight from the insert just performed, without consulting session state. currval('<sequence>') and lastval() work too, but lastval() has a catch of its own: it refers to the last sequence used at all, not to a particular table, so in a procedure inserting into several tables it is easy to get someone else's value."
    ),
    "AUTO_INCREMENT=<n> в опциях таблицы — следующее значение, которое выдаст счётчик; в дампе непустой таблицы оно всегда больше максимального существующего id. ora2pg (-m) переносит сам столбец корректно (он становится serial), но стартовое значение теряет: в выводе нет ни ALTER SEQUENCE ... RESTART WITH <n>, ни setval() (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-080-mysql-auto-increment-start.md). Схема загружается без единой ошибки, и последовательность начинает отсчёт с 1 — то есть с значений, которые в перенесённых данных уже заняты. Первая же вставка после миграции падает на нарушении первичного ключа, и так до тех пор, пока счётчик не догонит реальные данные. Чинится одной строкой на таблицу после загрузки данных: SELECT setval(pg_get_serial_sequence('<таблица>', '<столбец>'), (SELECT max(<столбец>) FROM <таблица>)).": (
        "AUTO_INCREMENT=<n> among the table options -- the next value the counter will hand out; in a dump of a non-empty table it is always greater than the largest existing id. ora2pg (-m) carries the column itself over correctly (it becomes serial) but loses the starting value: there is no ALTER SEQUENCE ... RESTART WITH <n> and no setval() anywhere in the output (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-080-mysql-auto-increment-start.md). The schema loads without a single error, and the sequence starts counting from 1 -- that is, from values the migrated data already occupies. The very first insert after the migration fails on a primary key violation, and keeps failing until the counter catches up with the real data. One line per table after the data is loaded fixes it: SELECT setval(pg_get_serial_sequence('<table>', '<column>'), (SELECT max(<column>) FROM <table>))."
    ),
    "DATE_FORMAT(<дата>, <формат>) — форматирование даты в строку по MySQL-овским спецификаторам (%Y, %m, %d, %H, %i, %s). ora2pg (-m) пытается перевести вызов и выдаёт то, что вызовом функции уже не является: имени to_char в выводе нет вообще, остаётся голая скобка с двумя выражениями через запятую — (d::varchar::timestamp, 'YYYY-MM-%d HH24:MI:SS'), то есть конструктор строки-кортежа. Заодно переведены не все спецификаторы: %Y/%m/%H/%i/%s стали YYYY/MM/HH24/MI/SS, а %d остался как был (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-081-mysql-date-format.md). Хуже всего то, что ошибки не будет ни на одном этапе: и загрузка, и вызов проходят успешно, потому что кортеж — совершенно законное выражение. Проверено на живых данных: вместо строки 2024-03-05 00:00:00 запрос возвращает пару из самой даты и недопереведённой строки формата. То есть в отчётах, выгрузках и API-ответах молча оказывается не то, что было. Чинится переписыванием на to_char(<дата>, 'YYYY-MM-DD HH24:MI:SS'), и каждый спецификатор формата стоит сверить вручную.": (
        "DATE_FORMAT(<date>, <format>) -- formatting a date into a string using MySQL's format specifiers (%Y, %m, %d, %H, %i, %s). ora2pg (-m) tries to translate the call and produces something that is no longer a function call at all: the to_char name is absent from the output entirely, leaving a bare parenthesis with two expressions separated by a comma -- (d::varchar::timestamp, 'YYYY-MM-%d HH24:MI:SS') -- that is, a row constructor. On top of that, not every specifier is translated: %Y/%m/%H/%i/%s became YYYY/MM/HH24/MI/SS, while %d was left as it was (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-081-mysql-date-format.md). The worst part is that nothing errors at any stage: both the load and the call succeed, because a tuple is a perfectly legal expression. Verified on live data: instead of the string 2024-03-05 00:00:00 the query returns a pair of the date itself and the half-translated format string. So reports, exports and API responses silently end up carrying something other than what was there. The fix is to rewrite it as to_char(<date>, 'YYYY-MM-DD HH24:MI:SS'), checking every format specifier by hand."
    ),
    'FOREIGN KEY — внешний ключ, объявленный в списке столбцов CREATE TABLE (в том числе в форме CONSTRAINT <имя> FOREIGN KEY ... REFERENCES ... ON DELETE CASCADE, которую выдаёт mysqldump). ora2pg (-m) выбрасывает его из вывода целиком: в сгенерированном файле нет ни одной строки FOREIGN KEY — ни в CREATE TABLE, ни отдельным ALTER TABLE после него (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-082-mysql-foreign-key.md; проверены обе формы — и с именем CONSTRAINT, и без него). Отдельного типа экспорта под внешние ключи у ora2pg нет: в списке поддерживаемых -t значений (TABLE, VIEW, TRIGGER, FUNCTION, PROCEDURE, PARTITION и т.д.) нет ни FKEY, ни CONSTRAINT, так что «они выгружаются отдельно» — не тот случай. Ошибки при этом не будет ни на загрузке, ни потом: схема поднимется, приложение заработает, и ссылочная целостность просто перестанет существовать — вместе с каскадными удалениями, если они были. Восстанавливается вручную: ALTER TABLE <таблица> ADD CONSTRAINT <имя> FOREIGN KEY (<столбцы>) REFERENCES <родитель> (<столбцы>) ON DELETE ... после загрузки всех таблиц.': (
        'FOREIGN KEY -- a foreign key declared in a CREATE TABLE column list (including the CONSTRAINT <name> FOREIGN KEY ... REFERENCES ... ON DELETE CASCADE form that mysqldump emits). ora2pg (-m) drops it from the output entirely: the generated file contains no FOREIGN KEY line at all -- neither inside CREATE TABLE nor as a separate ALTER TABLE after it (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-082-mysql-foreign-key.md; both forms were tested, with and without a CONSTRAINT name). ora2pg has no separate export type for foreign keys either: its list of supported -t values (TABLE, VIEW, TRIGGER, FUNCTION, PROCEDURE, PARTITION and so on) contains neither FKEY nor CONSTRAINT, so "they are exported separately" is not the explanation here. And no error appears at load time or later: the schema comes up, the application runs, and referential integrity simply ceases to exist -- along with the cascading deletes, if there were any. Restore it by hand: ALTER TABLE <table> ADD CONSTRAINT <name> FOREIGN KEY (<columns>) REFERENCES <parent> (<columns>) ON DELETE ... once all the tables are loaded.'
    ),
    "'0000-00-00' — «нулевая» дата MySQL/MariaDB: не настоящая дата, а признак «значение не задано», который MySQL допускает в DATE/DATETIME по историческим причинам. ora2pg (-m) молча подменяет её на '1970-01-01' — настоящую, осмысленную дату (начало эпохи Unix), — подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16 (docs/research/gap-083-mysql-zero-date.md): в сгенерированном DDL стоит DEFAULT '1970-01-01', и вставленная после миграции строка получает именно эту дату (проверено на живых данных). Ошибки нет ни на загрузке, ни потом — расхождение чисто смысловое и потому незаметное: запросы вида WHERE d = '0000-00-00' (поиск незаполненных) перестают находить что-либо, а отчёты по датам начинают показывать 1970 год как реальное событие. Правильный перенос — NULL (плюс, если нужно, NOT NULL снимается) или отдельный признак «не задано»; проверьте заодно и сами данные, а не только DEFAULT.": (
        '\'0000-00-00\' -- MySQL/MariaDB\'s zero date: not a real date but a marker for "no value set", which MySQL allows in DATE/DATETIME for historical reasons. ora2pg (-m) silently substitutes \'1970-01-01\' for it -- a real, meaningful date (the start of the Unix epoch) -- confirmed against a real ora2pg 25.0 + PostgreSQL 16 run (docs/research/gap-083-mysql-zero-date.md): the generated DDL carries DEFAULT \'1970-01-01\', and a row inserted after the migration gets exactly that date (verified on live data). There is no error at load time or later -- the divergence is purely one of meaning and therefore unnoticeable: queries like WHERE d = \'0000-00-00\' (looking for unfilled values) stop finding anything, and date reports start showing 1970 as a real event. The correct migration target is NULL (dropping NOT NULL if needed) or a separate "not set" flag; check the data itself as well, not just the DEFAULT.'
    ),
    'DECLARE ... HANDLER — обработчик условий в хранимой процедуре MySQL/MariaDB (CONTINUE/EXIT HANDLER FOR SQLEXCEPTION, FOR NOT FOUND, для конкретного SQLSTATE). ora2pg (-m) выбрасывает объявление из вывода целиком: на его месте в сгенерированном теле остаются пустые строки, и никакого BEGIN ... EXCEPTION WHEN ... взамен не появляется (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-084-mysql-declare-handler.md; проверены обе разновидности — CONTINUE HANDLER FOR NOT FOUND и EXIT HANDLER FOR SQLEXCEPTION). Ошибки нет ни на загрузке, ни при вызове: процедура просто теряет всю обработку ошибок разом, и последствия ровно противоположны исходному замыслу — то, что MySQL глушил и продолжал выполнение, теперь вылетает наружу и обрывает транзакцию вызывающего. Восстанавливается блоком BEGIN ... EXCEPTION WHEN <условие> THEN ... END вокруг нужного участка кода. Для NOT FOUND отдельного условия в PL/pgSQL нет — оно проверяется через FOUND или GET DIAGNOSTICS сразу после запроса, так что этот случай переписывается не в EXCEPTION, а в обычный IF.': (
        "DECLARE ... HANDLER -- a condition handler in a MySQL/MariaDB stored procedure (CONTINUE/EXIT HANDLER FOR SQLEXCEPTION, FOR NOT FOUND, for a specific SQLSTATE). ora2pg (-m) drops the declaration from the output entirely: blank lines are left where it was in the generated body, and no BEGIN ... EXCEPTION WHEN ... appears in its place (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-084-mysql-declare-handler.md; both variants were tested -- CONTINUE HANDLER FOR NOT FOUND and EXIT HANDLER FOR SQLEXCEPTION). No error appears at load time or on the call: the procedure simply loses all of its error handling at once, and the consequences are the exact opposite of the original intent -- what MySQL swallowed and carried on from now escapes and aborts the caller's transaction. Restore it with a BEGIN ... EXCEPTION WHEN <condition> THEN ... END block around the relevant code. NOT FOUND has no condition of its own in PL/pgSQL -- it is checked via FOUND or GET DIAGNOSTICS right after the query, so that case is rewritten as an ordinary IF rather than an EXCEPTION."
    ),
    "COLLATE / CHARACTER SET на столбце — правило сравнения и сортировки строк. ora2pg (-m) выбрасывает эту часть определения столбца из вывода целиком (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-085-mysql-collate.md). Ошибки не будет ни на загрузке, ни потом, но сравнение строк молча меняет смысл: типовые для MySQL правила вида utf8mb4_general_ci / utf8mb4_0900_ai_ci регистронезависимы, а сравнение в PostgreSQL по умолчанию — регистрозависимо. Проверено на живых данных: строка 'Alice', найденная в MySQL запросом WHERE name = 'alice', после миграции не находится вообще (0 строк). То есть ломается не схема, а выдача запросов — логины, поиск по имени, проверки уникальности начинают вести себя иначе, и заметно это только в бою. Восстанавливается либо явным COLLATE на столбце (в PostgreSQL доступны ICU-правила с нужной чувствительностью), либо типом citext, либо приведением обеих сторон сравнения к lower().": (
        "COLLATE / CHARACTER SET on a column -- the rule for comparing and sorting strings. ora2pg (-m) drops this part of the column definition from the output entirely (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-085-mysql-collate.md). No error appears at load time or later, but string comparison silently changes meaning: MySQL's typical rules such as utf8mb4_general_ci / utf8mb4_0900_ai_ci are case-insensitive, whereas comparison in PostgreSQL is case-sensitive by default. Verified on live data: the row 'Alice', which MySQL found with WHERE name = 'alice', is not found at all after the migration (0 rows). So what breaks is not the schema but what queries return -- logins, name search, uniqueness checks start behaving differently, and it only shows in production. Restore it either with an explicit COLLATE on the column (PostgreSQL offers ICU rules with the sensitivity you need), or with the citext type, or by applying lower() to both sides of the comparison."
    ),
    "SET('a','b',...) — тип MySQL/MariaDB для набора значений: в столбце может лежать любое подмножество перечисленного списка сразу (хранится битовой маской). ora2pg (-m) отображает его в обычный text (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-086-mysql-set-type.md). Ошибки нет ни на загрузке, ни потом, и уже накопленные данные переносятся как есть — теряется ровно проверка: после миграции в столбец можно записать любую строку, включая значение не из списка и мусор. Severity здесь medium, а не high, в отличие от родственного ENUM (GAP-068): ENUM ломает загрузку схемы наглухо, а тут схема поднимается и работает, и вопрос только в проверке будущих записей. Восстанавливается либо CHECK-ограничением, либо массивом с проверкой на допустимые элементы, либо отдельной таблицей связей — что честнее всего, если значений много.": (
        "SET('a','b',...) -- MySQL/MariaDB's type for a set of values: the column can hold any subset of the listed values at once (stored as a bitmask). ora2pg (-m) maps it onto plain text (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-086-mysql-set-type.md). No error appears at load time or later, and data already accumulated carries over as-is -- what is lost is precisely the validation: after the migration any string at all can be written into the column, including a value not in the list, and outright garbage. The severity here is medium rather than high, unlike the related ENUM (GAP-068): ENUM breaks the schema load outright, whereas here the schema comes up and works, and the only question is validating future writes. Restore it either with a CHECK constraint, or with an array plus a check on allowed elements, or with a separate link table -- which is the most honest option when there are many values."
    ),
    'Идентификаторы в квадратных скобках ([dbo].[Orders], [Id], [int]) — штатный способ записи имён в T-SQL, и именно так их выводит SSMS и Generate Scripts по умолчанию, то есть так выглядит практически любой реальный скрипт. При файловом экспорте (-M -i <файл>) ora2pg скобки не снимает: они остаются частью имени и потом ещё берутся в двойные кавычки. Из CREATE TABLE [dbo].[Orders] ( [Id] [int] ... ) получается CREATE TABLE "[dbo]"."[orders]" ( "[id]" [INT] ... ), то есть таблица с именем [orders] в схеме [dbo] и столбец типа [INT], которого не существует. Подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16 (docs/research/gap-087-mssql-bracket-identifier.md): загрузка падает сразу — \'syntax error at or near "["\'. Та же таблица, записанная без скобок, конвертируется корректно, так что дело именно в них. Причина видна в исходниках ora2pg: снятие скобок (s/[\\[\\]]+//g) есть в MSSQL.pm, но только в подпрограммах, работающих с живым подключением (_column_info, _get_views, _get_functions, _get_procedures, _column_attributes и другие) — файловый путь через -i до них не доходит. Отсюда и обход: либо экспортировать через живое подключение к SQL Server, либо снять скобки в скрипте до конвертации.': (
        'Bracket-quoted identifiers ([dbo].[Orders], [Id], [int]) are T-SQL\'s standard way of writing names, and are exactly what SSMS and Generate Scripts emit by default -- which is to say, what practically every real-world script looks like. On the file-based path (-M -i <file>) ora2pg does not strip them: they stay part of the name and are then wrapped in double quotes on top. CREATE TABLE [dbo].[Orders] ( [Id] [int] ... ) becomes CREATE TABLE "[dbo]"."[orders]" ( "[id]" [INT] ... ) -- a table named [orders] in a schema named [dbo], with a column of the non-existent type [INT]. Confirmed against a real ora2pg 25.0 + PostgreSQL 16 run (docs/research/gap-087-mssql-bracket-identifier.md): the load fails immediately with \'syntax error at or near "["\'. The same table written without brackets converts correctly, so the brackets really are the cause. ora2pg\'s own source shows why: the bracket-stripping (s/[\\[\\]]+//g) does exist in MSSQL.pm, but only inside the subroutines that work against a live connection (_column_info, _get_views, _get_functions, _get_procedures, _column_attributes and others) -- the file-based -i path never reaches them. Hence the workaround: either export through a live SQL Server connection, or strip the brackets from the script before converting.'
    ),
    'NEWID() / NEWSEQUENTIALID() — генерация GUID по умолчанию в SQL Server. ora2pg (-M) выбирает правильную цель — uuid_generate_v4(), — но строку CREATE EXTENSION IF NOT EXISTS "uuid-ossp", без которой этой функции не существует, в вывод не добавляет (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-088-mssql-newid-default.md). CREATE TABLE падает немедленно, при загрузке схемы: \'function uuid_generate_v4() does not exist\'. Показательно, что в том же прогоне ora2pg сам выводит CREATE EXTENSION citext, когда он ему нужен под строковые типы, — то есть механизм подключения расширений у него есть и просто не применяется здесь. Чинится одной строкой CREATE EXTENSION IF NOT EXISTS "uuid-ossp" перед загрузкой схемы; как вариант, в PostgreSQL 13+ можно обойтись встроенной gen_random_uuid() вообще без расширения.': (
        'NEWID() / NEWSEQUENTIALID() -- SQL Server\'s default GUID generation. ora2pg (-M) picks the right target, uuid_generate_v4(), but does not add the CREATE EXTENSION IF NOT EXISTS "uuid-ossp" line without which that function does not exist (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-088-mssql-newid-default.md). CREATE TABLE fails immediately, at schema load time: \'function uuid_generate_v4() does not exist\'. Tellingly, in the same run ora2pg does emit CREATE EXTENSION citext by itself when it needs it for string types -- so the mechanism for wiring up extensions is there and simply isn\'t applied here. One line fixes it: CREATE EXTENSION IF NOT EXISTS "uuid-ossp" before loading the schema; alternatively, PostgreSQL 13+ has the built-in gen_random_uuid() and needs no extension at all.'
    ),
    'UPDATE ... SET — обычное обновление строк. ora2pg (-M) путает это SET с одноимённым оператором присваивания переменной в T-SQL (SET @x = 1) и переписывает конструкцию по правилам присваивания: само слово SET из запроса пропадает, а первое присваивание получает := вместо = (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-089-mssql-update-set.md). Из UPDATE orders SET amount = @x, nm = \'y\' WHERE id = 1 получается UPDATE orders amount := p_x, nm = \'y\' WHERE id = 1. Загрузка проходит чисто — ora2pg выставляет в своём выводе check_function_bodies = false, — а при первом же реальном вызове процедура падает с \'syntax error at or near ":="\'. Под это попадает каждый UPDATE в каждой процедуре, так что после конвертации их придётся просмотреть все: правится возвратом к обычному SQL — UPDATE <таблица> SET <столбец> = <значение>.': (
        'UPDATE ... SET -- an ordinary row update. ora2pg (-M) confuses this SET with T-SQL\'s identically named variable-assignment statement (SET @x = 1) and rewrites the construct by assignment rules: the query\'s SET keyword disappears and the first assignment gets := instead of = (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-089-mssql-update-set.md). UPDATE orders SET amount = @x, nm = \'y\' WHERE id = 1 comes out as UPDATE orders amount := p_x, nm = \'y\' WHERE id = 1. The load is clean -- ora2pg sets check_function_bodies = false in its output -- and on the very first real call the routine fails with \'syntax error at or near ":="\'. This catches every UPDATE in every procedure, so after conversion they all need reviewing; the fix is a return to ordinary SQL: UPDATE <table> SET <column> = <value>.'
    ),
    'IDENTITY(<начало>, <шаг>) — автоинкрементный столбец SQL Server. ora2pg (-M) выбрасывает это свойство целиком: столбец становится обычным integer, и ни serial, ни GENERATED ... AS IDENTITY, ни отдельной последовательности в выводе не появляется (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-090-mssql-identity-column.md). Схема при этом загружается без единой ошибки, поэтому проблему видно только при первой же обычной вставке — проверено на живых данных: INSERT INTO invoices (amount) VALUES (9.99) падает с \'null value in column "id" violates not-null constraint\', тогда как в SQL Server ровно тот же INSERT проходит. Обратите внимание на разницу с MySQL-стороной того же ora2pg: там AUTO_INCREMENT корректно превращается в serial и теряется только стартовое значение (GAP-080), здесь же не остаётся ничего. Чинится заменой типа на GENERATED BY DEFAULT AS IDENTITY (или serial) с последующей установкой счётчика по максимуму перенесённых данных.': (
        'IDENTITY(<seed>, <increment>) -- SQL Server\'s auto-incrementing column. ora2pg (-M) drops the property entirely: the column becomes a plain integer, and neither serial, nor GENERATED ... AS IDENTITY, nor a separate sequence appears anywhere in the output (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-090-mssql-identity-column.md). The schema loads without a single error, so the problem only shows on the first ordinary insert -- verified on live data: INSERT INTO invoices (amount) VALUES (9.99) fails with \'null value in column "id" violates not-null constraint\', while in SQL Server that exact INSERT succeeds. Note the contrast with the same ora2pg\'s MySQL side: there AUTO_INCREMENT correctly becomes serial and only the starting value is lost (GAP-080), whereas here nothing survives at all. Fix by changing the type to GENERATED BY DEFAULT AS IDENTITY (or serial) and then setting the counter from the maximum of the migrated data.'
    ),
    'Процедура без параметров. Само по себе это ничем не примечательно, но ora2pg (-M) генерирует для неё пустой блок объявлений — DECLARE, пустая строка и одинокая точка с запятой, — который PL/pgSQL разобрать не может (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-091-mssql-parameterless-procedure.md). Проверено прямым сравнением: у процедуры с параметром блока DECLARE в выводе нет вовсе и тело начинается сразу с BEGIN, а у точно такой же процедуры без параметров появляется сломанный DECLARE. Загрузка проходит без ошибок — ora2pg выставляет в своём выводе check_function_bodies = false, поэтому тело не разбирается, — и падение происходит при первом же реальном вызове: \'syntax error at or near ";"\'. Под это попадает каждая процедура без параметров, то есть, как правило, все служебные и отчётные. Чинится удалением пустого DECLARE из готового кода (или добавлением в него реальных переменных, если они там нужны).': (
        'A procedure with no parameters. Unremarkable in itself, but ora2pg (-M) generates an empty declaration block for it -- DECLARE, a blank line and a lone semicolon -- which PL/pgSQL cannot parse (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-091-mssql-parameterless-procedure.md). Verified by direct comparison: a procedure with a parameter gets no DECLARE block at all and its body starts straight at BEGIN, while the very same procedure without parameters gets the broken DECLARE. The load succeeds without errors -- ora2pg sets check_function_bodies = false in its output, so the body is not parsed -- and the failure happens on the very first real call: \'syntax error at or near ";"\'. This catches every parameterless procedure, which as a rule means all the housekeeping and reporting ones. Fix by deleting the empty DECLARE from the generated code (or by putting real variables in it, if it needs any).'
    ),
    'IF — условный оператор T-SQL. ora2pg (-M) не доводит перевод до конца ни в одной из двух его форм, причём ломается по-разному (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-092-mssql-if-statement.md). С блоком — IF @x < 0 BEGIN ... END — слово THEN подставляется правильно, но закрывающее END так и остаётся END вместо END IF, и разбор падает с \'syntax error at or near "END"\'. Без блока — IF @x < 0 <оператор>; — не подставляется и THEN, и падение другое: \'missing "THEN" at end of SQL expression\'. Загрузка в обоих случаях проходит чисто (check_function_bodies = false в выводе ora2pg), ошибка вылезает при первом вызове. Переписывается в полную форму PL/pgSQL: IF <условие> THEN <операторы>; END IF;': (
        'IF -- T-SQL\'s conditional statement. ora2pg (-M) fails to finish the translation in either of its two shapes, and breaks differently in each (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-092-mssql-if-statement.md). With a block -- IF @x < 0 BEGIN ... END -- the THEN is inserted correctly, but the closing END stays END instead of END IF, and parsing fails with \'syntax error at or near "END"\'. Without a block -- IF @x < 0 <statement>; -- no THEN is inserted either, and the failure differs: \'missing "THEN" at end of SQL expression\'. In both cases the load is clean (check_function_bodies = false in ora2pg\'s output) and the error surfaces on the first call. Rewrite in PL/pgSQL\'s full form: IF <condition> THEN <statements>; END IF;'
    ),
    "RAISERROR / THROW — операторы возбуждения ошибки в T-SQL. ora2pg (-M) копирует оба в тело процедуры дословно (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-093-mssql-raiserror.md). В PL/pgSQL нет ни того, ни другого. Загрузка проходит чисто — ora2pg выставляет в своём выводе check_function_bodies = false, — и падение происходит при первом же реальном вызове. Переписывается на RAISE EXCEPTION '<текст>' USING ERRCODE = '<sqlstate>'. При переносе стоит помнить о разнице: severity в RAISERROR (второй аргумент) в PostgreSQL соответствует не коду ошибки, а уровню сообщения — RAISE NOTICE / WARNING / EXCEPTION, — а номера ошибок из THROW (>= 50000) нужно отобразить на пятизначные SQLSTATE самостоятельно.": (
        "RAISERROR / THROW -- T-SQL's error-raising statements. ora2pg (-M) copies both into the procedure body verbatim (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-093-mssql-raiserror.md). PL/pgSQL has neither. The load is clean -- ora2pg sets check_function_bodies = false in its output -- and the failure happens on the very first real call. Rewrite as RAISE EXCEPTION '<text>' USING ERRCODE = '<sqlstate>'. Mind the difference while porting: RAISERROR's severity (its second argument) corresponds not to an error code in PostgreSQL but to a message level -- RAISE NOTICE / WARNING / EXCEPTION -- and THROW's error numbers (>= 50000) have to be mapped onto five-character SQLSTATEs yourself."
    ),
    'BEGIN TRY ... END TRY BEGIN CATCH ... END CATCH — обработка ошибок в T-SQL. ora2pg (-M) копирует всю конструкцию в тело процедуры дословно, включая END TRY и END CATCH (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-094-mssql-try-catch.md). В PL/pgSQL обработка ошибок пишется иначе — BEGIN ... EXCEPTION WHEN <условие> THEN ... END, — и такого синтаксиса там нет. Загрузка проходит чисто (check_function_bodies = false в выводе ora2pg), падение — при первом реальном вызове. Переписывается на блок BEGIN ... EXCEPTION WHEN OTHERS THEN ... END, причём вызовы вида ERROR_MESSAGE() внутри CATCH заменяются на SQLERRM, а ERROR_NUMBER() — на SQLSTATE.': (
        "BEGIN TRY ... END TRY BEGIN CATCH ... END CATCH -- T-SQL's error handling. ora2pg (-M) copies the whole construct into the procedure body verbatim, END TRY and END CATCH included (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-094-mssql-try-catch.md). PL/pgSQL spells error handling differently -- BEGIN ... EXCEPTION WHEN <condition> THEN ... END -- and has no such syntax. The load is clean (check_function_bodies = false in ora2pg's output); the failure comes on the first real call. Rewrite as a BEGIN ... EXCEPTION WHEN OTHERS THEN ... END block, replacing calls like ERROR_MESSAGE() inside the CATCH with SQLERRM, and ERROR_NUMBER() with SQLSTATE."
    ),
    'SELECT TOP <n> — ограничение числа строк в T-SQL. ora2pg (-M) копирует конструкцию в тело процедуры дословно (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-095-mssql-top-clause.md). В PostgreSQL оператора TOP нет вообще, и разбор падает на числе сразу за ним: \'syntax error at or near "10"\'. Загрузка при этом проходит чисто (check_function_bodies = false в выводе ora2pg), ошибка вылезает при первом вызове. Переписывается на LIMIT <n> в конце запроса. Отдельно проверьте TOP без ORDER BY: в T-SQL так пишут часто, и при переносе на LIMIT порядок строк остаётся столь же неопределённым — если на него полагались, нужен явный ORDER BY. Форма TOP (<n>) PERCENT прямого аналога не имеет вовсе и требует отдельного пересчёта.': (
        'SELECT TOP <n> -- T-SQL\'s row limit. ora2pg (-M) copies the construct into the procedure body verbatim (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-095-mssql-top-clause.md). PostgreSQL has no TOP at all, and parsing fails on the number right after it: \'syntax error at or near "10"\'. The load is clean (check_function_bodies = false in ora2pg\'s output) and the error surfaces on the first call. Rewrite as LIMIT <n> at the end of the query. Check TOP without ORDER BY separately: it is written that way often in T-SQL, and moving it to LIMIT leaves the row order just as undefined -- if anything relied on it, an explicit ORDER BY is needed. The TOP (<n>) PERCENT form has no direct equivalent at all and needs recomputing.'
    ),
    'SCOPE_IDENTITY() / @@IDENTITY / IDENT_CURRENT() — способы узнать значение, выданное IDENTITY при последней вставке в SQL Server. ora2pg (-M) копирует вызов в тело процедуры дословно (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-096-mssql-scope-identity.md). Ни такой функции, ни такой системной переменной в PostgreSQL нет, и при первом же реальном вызове процедура падает; загрузка проходит чисто, потому что ora2pg выставляет в своём выводе check_function_bodies = false. Переписывается лучше всего на INSERT ... RETURNING <столбец> INTO <переменная>: значение берётся прямо из выполненной вставки. Учтите, что сам столбец IDENTITY при этом тоже теряется (GAP-090), так что возвращать может быть уже нечего — эти два места правятся вместе.': (
        'SCOPE_IDENTITY() / @@IDENTITY / IDENT_CURRENT() -- the ways to read back the value IDENTITY produced on the last insert in SQL Server. ora2pg (-M) copies the call into the procedure body verbatim (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-096-mssql-scope-identity.md). PostgreSQL has neither such a function nor such a system variable, and the routine fails on its very first real call; the load is clean because ora2pg sets check_function_bodies = false in its output. The best rewrite is INSERT ... RETURNING <column> INTO <variable>, which takes the value straight from the insert just performed. Note that the IDENTITY column itself is lost too (GAP-090), so there may be nothing left to return -- these two places get fixed together.'
    ),
    'OUTPUT INSERTED.<столбец> / OUTPUT DELETED.<столбец> — возврат затронутых строк прямо из INSERT/UPDATE/DELETE в T-SQL. ora2pg (-M) копирует оговорку в тело процедуры дословно (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-097-mssql-output-clause.md). В PostgreSQL та же идея пишется как RETURNING, и слова OUTPUT он не понимает. Загрузка проходит чисто (check_function_bodies = false в выводе ora2pg), падение — при первом вызове. Переписывается на RETURNING <столбец>, но с оглядкой на две вещи: RETURNING не различает INSERTED и DELETED (для UPDATE он возвращает новые значения — старые придётся брать иначе), и в отличие от OUTPUT ... INTO <таблица> его результат нельзя направить в таблицу одним оператором.': (
        "OUTPUT INSERTED.<column> / OUTPUT DELETED.<column> -- returning affected rows straight out of an INSERT/UPDATE/DELETE in T-SQL. ora2pg (-M) copies the clause into the procedure body verbatim (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-097-mssql-output-clause.md). PostgreSQL spells the same idea RETURNING and does not understand the word OUTPUT. The load is clean (check_function_bodies = false in ora2pg's output); the failure comes on the first call. Rewrite as RETURNING <column>, with two caveats: RETURNING does not distinguish INSERTED from DELETED (for an UPDATE it returns the new values -- the old ones have to be captured some other way), and unlike OUTPUT ... INTO <table> its result cannot be directed into a table in one statement."
    ),
    'IIF(<условие>, <если да>, <если нет>) — тернарный выбор в T-SQL. ora2pg (-M) копирует вызов в тело процедуры дословно (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-098-mssql-iif.md). Функции IIF в PostgreSQL нет, и при первом же реальном вызове процедура падает; загрузка проходит чисто, потому что ora2pg выставляет в своём выводе check_function_bodies = false. Показательно, что в том же операторе ora2pg соседний CHARINDEX перевести пытается (и делает это неверно, см. GAP-100), то есть IIF просто не входит в его таблицу соответствий. Переписывается на CASE WHEN <условие> THEN <если да> ELSE <если нет> END.': (
        "IIF(<condition>, <if true>, <if false>) -- T-SQL's ternary choice. ora2pg (-M) copies the call into the procedure body verbatim (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-098-mssql-iif.md). PostgreSQL has no IIF function, and the routine fails on its very first real call; the load is clean because ora2pg sets check_function_bodies = false in its output. Tellingly, in the same statement ora2pg does try to translate the neighbouring CHARINDEX (and gets it wrong -- see GAP-100), so IIF is simply absent from its mapping table. Rewrite as CASE WHEN <condition> THEN <if true> ELSE <if false> END."
    ),
    'DATEDIFF(<единица>, <начало>, <конец>) — разница дат в T-SQL. ora2pg (-M) копирует вызов в тело процедуры дословно (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-099-mssql-datediff.md), хотя соседние DATEADD и DATEPART в том же операторе переводит правильно — в арифметику с INTERVAL и в date_part(). Функции DATEDIFF в PostgreSQL нет; загрузка проходит чисто (check_function_bodies = false в выводе ora2pg), падение — при первом вызове. Переписывается через вычитание: разница в днях — (<конец>::date - <начало>::date), в остальных единицах — через EXTRACT(EPOCH FROM (<конец> - <начало>)) с делением. Обратите внимание на семантику: T-SQL DATEDIFF считает пересечённые границы единиц, а не полные интервалы, поэтому DATEDIFF(year, ...) между 31 декабря и 1 января даёт 1 — прямое вычитание даст 0.': (
        "DATEDIFF(<unit>, <start>, <end>) -- T-SQL's date difference. ora2pg (-M) copies the call into the procedure body verbatim (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-099-mssql-datediff.md), even though it translates the neighbouring DATEADD and DATEPART in the same statement correctly -- into INTERVAL arithmetic and date_part(). PostgreSQL has no DATEDIFF function; the load is clean (check_function_bodies = false in ora2pg's output), the failure comes on the first call. Rewrite with subtraction: a difference in days is (<end>::date - <start>::date), other units go through EXTRACT(EPOCH FROM (<end> - <start>)) with division. Mind the semantics: T-SQL's DATEDIFF counts unit boundaries crossed rather than whole intervals, so DATEDIFF(year, ...) between 31 December and 1 January gives 1 where plain subtraction gives 0."
    ),
    'CHARINDEX(<что искать>, <где искать>) — поиск подстроки в T-SQL. В отличие от прочих встроенных функций этой партии, ora2pg (-M) её переводить пытается — и выбирает верную цель, position(... in ...), — но удваивает кавычки вокруг искомой строки: из CHARINDEX(\'abc\', @nm) получается position(\'\'abc\'\' in p_nm) (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-100-mssql-charindex.md). Это уже не валидный SQL: разбор падает с \'syntax error at or near "abc"\'. Загрузка проходит чисто (check_function_bodies = false в выводе ora2pg), ошибка вылезает при первом вызове. Чинится снятием лишних кавычек: position(\'abc\' in p_nm). Имейте в виду, что у CHARINDEX есть третий аргумент — позиция начала поиска, — которому у position() прямого соответствия нет и который переносится через substring().': (
        'CHARINDEX(<needle>, <haystack>) -- T-SQL\'s substring search. Unlike the other builtins in this batch, ora2pg (-M) does try to translate it -- and picks the right target, position(... in ...) -- but doubles the quotes around the search string: CHARINDEX(\'abc\', @nm) comes out as position(\'\'abc\'\' in p_nm) (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-100-mssql-charindex.md). That is no longer valid SQL: parsing fails with \'syntax error at or near "abc"\'. The load is clean (check_function_bodies = false in ora2pg\'s output) and the error surfaces on the first call. Fix by removing the extra quotes: position(\'abc\' in p_nm). Bear in mind that CHARINDEX has a third argument -- the position to start searching from -- which position() has no direct equivalent for and which is carried over via substring().'
    ),
    'Фильтрованный индекс (CREATE INDEX ... WHERE <условие>) — индекс по части строк таблицы. ora2pg (-M) выбрасывает такой оператор целиком: в выводе не появляется никакого индекса вообще (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-101-mssql-filtered-index.md). Обиднее всего, что переносить тут почти нечего: в PostgreSQL есть ровно такие же частичные индексы и ровно с тем же синтаксисом — CREATE INDEX ... ON ... WHERE ..., — а обычный CREATE NONCLUSTERED INDEX ... INCLUDE (...) тот же ora2pg в том же прогоне переносит корректно. Ошибки не будет ни на загрузке, ни потом: схема поднимется без индекса, и разница проявится как деградация планов на больших таблицах, а если индекс был UNIQUE — ещё и как исчезнувшее ограничение уникальности. Восстанавливается дословным переносом оператора после загрузки схемы.': (
        "A filtered index (CREATE INDEX ... WHERE <condition>) -- an index over part of a table's rows. ora2pg (-M) drops the whole statement: no index appears in the output at all (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-101-mssql-filtered-index.md). What makes it especially annoying is how little there was to port: PostgreSQL has exactly the same partial indexes with exactly the same syntax -- CREATE INDEX ... ON ... WHERE ... -- and an ordinary CREATE NONCLUSTERED INDEX ... INCLUDE (...) is carried over correctly by the same ora2pg in the same run. No error appears at load time or later: the schema comes up without the index, and the difference shows as degraded plans on large tables -- or, if the index was UNIQUE, as a vanished uniqueness constraint. Restore it by carrying the statement over as-is after the schema loads."
    ),
    'FOREIGN KEY — внешний ключ, объявленный в списке столбцов CREATE TABLE (в том числе в форме CONSTRAINT <имя> FOREIGN KEY ... REFERENCES ... ON DELETE CASCADE, которую выдаёт SSMS). ora2pg (-M) выбрасывает его из вывода целиком: строк FOREIGN KEY в сгенерированном файле нет ни одной — ни внутри CREATE TABLE, ни отдельным ALTER TABLE после него (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-102-mssql-foreign-key.md). Отдельного типа экспорта под внешние ключи у ora2pg нет: в списке поддерживаемых -t значений нет ни FKEY, ни CONSTRAINT. Ошибки не будет ни на загрузке, ни потом: схема поднимется, приложение заработает, и ссылочная целостность просто перестанет существовать — вместе с каскадными удалениями. Ровно то же самое ora2pg делает с внешними ключами на MySQL-стороне (GAP-082), так что это не особенность одного диалекта. Восстанавливается вручную: ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY ... REFERENCES ... после загрузки всех таблиц.': (
        'FOREIGN KEY -- a foreign key declared in a CREATE TABLE column list (including the CONSTRAINT <name> FOREIGN KEY ... REFERENCES ... ON DELETE CASCADE form that SSMS emits). ora2pg (-M) drops it from the output entirely: there is not a single FOREIGN KEY line in the generated file -- neither inside CREATE TABLE nor as a separate ALTER TABLE after it (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-102-mssql-foreign-key.md). ora2pg has no separate export type for foreign keys either: its list of supported -t values contains neither FKEY nor CONSTRAINT. And no error appears at load time or later: the schema comes up, the application runs, and referential integrity simply ceases to exist -- along with the cascading deletes. The same ora2pg does exactly the same thing to foreign keys on the MySQL side (GAP-082), so this is not a quirk of one dialect. Restore it by hand: ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY ... REFERENCES ... once all the tables are loaded.'
    ),
    "COLLATE на столбце — правило сравнения и сортировки строк в SQL Server. ora2pg (-M) выбрасывает оговорку из определения столбца, а сам столбец отображает в citext — регистронезависимый тип (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-103-mssql-collation.md). Для исходных правил с _CI_ (case-insensitive) это попадание в цель, а вот для _CS_ (case-sensitive) — молчаливая подмена смысла на противоположный. Проверено на живых данных: столбец с COLLATE SQL_Latin1_General_CP1_CS_AS после миграции находит строку 'ABC' по запросу WHERE code = 'abc' (1 строка), тогда как SQL Server с этим правилом не нашёл бы ничего. Ошибки при этом нет ни на одном этапе — меняется только выдача запросов, и заметно это в бою: ломаются проверки уникальности, поиск по коду, сравнение идентификаторов. Чинится заменой citext на text с явным COLLATE нужной чувствительности (в PostgreSQL для этого есть ICU-правила).": (
        "COLLATE on a column -- SQL Server's string comparison and sorting rule. ora2pg (-M) drops the clause from the column definition and maps the column onto citext, a case-insensitive type (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-103-mssql-collation.md). For source rules with _CI_ (case-insensitive) that lands on target; for _CS_ (case-sensitive) it silently swaps the meaning for its opposite. Verified on live data: a column with COLLATE SQL_Latin1_General_CP1_CS_AS finds the row 'ABC' for the query WHERE code = 'abc' after migration (1 row), where SQL Server under that rule would have found nothing. No error appears at any stage -- only what queries return changes, and it shows in production: uniqueness checks, code lookups and identifier comparisons all break. Fix by replacing citext with text plus an explicit COLLATE of the required sensitivity (PostgreSQL offers ICU rules for this)."
    ),
    "Вычисляемый столбец (<имя> AS (<выражение>), с PERSISTED или без) — столбец SQL Server, значение которого считается из других столбцов. ora2pg (-M) строит под него триггер BEFORE INSERT OR UPDATE — сам по себе подход рабочий, — но тип самого столбца выводит как citext независимо от того, что считает выражение (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-104-mssql-computed-column.md). Проверено: для total AS (price * qty) PERSISTED, где price numeric(10,2) и qty int, в готовой таблице столбец total имеет тип citext, то есть текст. Ошибки нет ни на загрузке, ни при вставке — значение посчитается и запишется, — но дальше это уже строка: сортировка идёт лексикографически ('100' < '20'), сравнение с числом и SUM() по столбцу падают или дают не то. Кроме того, в тело триггера попадает служебное слово PERSISTED, которое PostgreSQL молча трактует как псевдоним столбца. Чинится заменой типа столбца на тот, что реально считает выражение, а лучше — переносом на штатный GENERATED ALWAYS AS (...) STORED.": (
        "A computed column (<name> AS (<expression>), with or without PERSISTED) -- a SQL Server column whose value is derived from other columns. ora2pg (-M) builds a BEFORE INSERT OR UPDATE trigger for it -- a workable approach in itself -- but types the column as citext regardless of what the expression computes (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-104-mssql-computed-column.md). Verified: for total AS (price * qty) PERSISTED, where price is numeric(10,2) and qty is int, the finished table's total column has type citext -- that is, text. No error appears at load time or on insert -- the value is computed and stored -- but from then on it is a string: sorting is lexicographic ('100' < '20'), and comparison against a number or SUM() over the column fails or gives the wrong answer. On top of that the keyword PERSISTED ends up inside the trigger body, where PostgreSQL silently reads it as a column alias. Fix by giving the column the type its expression actually computes, or better, by moving it to a proper GENERATED ALWAYS AS (...) STORED."
    ),
    'ROWVERSION — столбец SQL Server, значение которого сервер сам меняет при каждом изменении строки; на нём обычно построена оптимистичная блокировка (UPDATE ... WHERE rv = <прочитанное значение>). ora2pg (-M) отображает его в обычный bytea (подтверждено реальным прогоном ora2pg 25.0 + PostgreSQL 16, docs/research/gap-105-mssql-rowversion.md). Тип по размеру подходит, но главного — самообновления — у bytea нет: после миграции значение не меняется никогда. Ошибки не будет ни на одном этапе, и это самое опасное: проверка WHERE rv = <старое значение> теперь совпадает всегда, то есть конфликт одновременных правок перестаёт обнаруживаться и правки молча затирают друг друга. Восстанавливается триггером BEFORE UPDATE, увеличивающим счётчик версии, либо переходом на xmin — системный столбец PostgreSQL, который меняется при каждом обновлении строки сам. Отдельно проверьте столбцы типа timestamp: в T-SQL это устаревший синоним ROWVERSION, и этот детектор его намеренно не помечает, чтобы не путать со столбцом, который просто называется timestamp.': (
        "ROWVERSION -- a SQL Server column whose value the server changes itself on every modification of the row; optimistic locking is usually built on it (UPDATE ... WHERE rv = <the value that was read>). ora2pg (-M) maps it onto a plain bytea (confirmed against a real ora2pg 25.0 + PostgreSQL 16 run, docs/research/gap-105-mssql-rowversion.md). The type fits by size, but bytea has none of the point of it -- the self-updating -- so after the migration the value never changes at all. No error appears at any stage, and that is the dangerous part: the check WHERE rv = <old value> now always matches, so concurrent-edit conflicts stop being detected and edits silently overwrite one another. Restore it with a BEFORE UPDATE trigger incrementing a version counter, or by switching to xmin -- PostgreSQL's system column, which changes on every row update by itself. Check columns of type timestamp separately: in T-SQL that is the deprecated synonym for ROWVERSION, and this detector deliberately does not flag it, to avoid confusion with a column that is merely named timestamp."
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
    "match_recognize": "Rewrite using window functions (LAG/LEAD over the partition) plus "
    "filtering, or a recursive CTE — PostgreSQL has no row pattern matching equivalent",
    "connect_by_pseudocolumn": "Carry the branch root through an extra recursive-CTE column, "
    "compute the leaf flag with a NOT EXISTS subquery, and the cycle flag with the CTE's "
    "own CYCLE clause (PostgreSQL 14+)",
    "keep_dense_rank": "Rewrite as a FIRST_VALUE/LAST_VALUE window function with the same "
    "ORDER BY inside OVER, or as DISTINCT ON, or as an aggregate with FILTER",
    "multiset_operator": "Move to PostgreSQL's array model: CAST(MULTISET(...)) → "
    "ARRAY(SELECT ...), MULTISET UNION → ||, MEMBER OF → = ANY(...), SUBMULTISET OF → <@",
    "sample_clause": "Replace with TABLESAMPLE: SAMPLE (n) → TABLESAMPLE BERNOULLI (n), "
    "SAMPLE BLOCK (n) → TABLESAMPLE SYSTEM (n)",
    "accessible_by": "No direct equivalent — move the subprogram into its own schema and "
    "restrict it with GRANT/REVOKE (role-level protection, not per-calling-subprogram)",
    "local_time_zone": "Change the column type to timestamptz — that is the type that "
    "reproduces the session-time-zone conversion Oracle's LTZ performs",
    "temporal_validity": "Expand into an ordinary pair of timestamp columns filtered in "
    "queries, or a tstzrange column with an exclusion constraint if overlap control is needed",
    "bitmap_index": "Replace with a plain btree (the planner combines several of them via "
    "bitmap scan on its own) or with gin plus an explicit operator class from btree_gin",
    "object_table": "Expand the object table into an ordinary one: a separate column per type "
    "attribute plus explicit constraints",
    "ignore_nulls": "Emulate it by hand: a grouping key from count(col) FILTER (WHERE col IS "
    "NOT NULL) plus first_value within the group, or a lateral subquery",
    "nlssort": "Map the Oracle sort name onto a real PostgreSQL locale (GERMAN → "
    '"de-DE-x-icu" or "de_DE.utf8") and create it with CREATE COLLATION if needed',
    "long_raw_type": "Change the column type to bytea — which is ora2pg's own documented "
    "mapping for LONG RAW",
    "anydata_type": "Remodel the column as jsonb, or split it into several typed columns plus "
    "a discriminator",
    "system_trigger": "Move DDL events onto PostgreSQL event triggers (CREATE EVENT TRIGGER); "
    "LOGON/LOGOFF/SERVERERROR belong in server logging or application logic instead",
    "trigger_follows": "Drop the clause and get the order you need from trigger names "
    "(PostgreSQL fires them alphabetically) or by merging the triggers into one",
    "table_collection": "Replace with unnest(...) for an array, or a plain set-returning "
    "function call in FROM — depending on what the collection itself became",
    "cursor_expression": "Replace with a join that aggregates the child rows (array_agg/"
    "json_agg), or with a separate function returning refcursor",
    "for_update_wait": "Drop WAIT n and set the timeout at session level instead: SET LOCAL "
    "lock_timeout = 'n s' before SELECT ... FOR UPDATE",
    "rownum_dml": "Rewrite through a primary-key subquery — DELETE FROM t WHERE id IN (SELECT "
    "id FROM t WHERE ... ORDER BY ... LIMIT n)",
    "to_date_rr": "Replace RR with an explicit four-digit YYYY after normalising the input "
    "— PostgreSQL does not know RR (it silently returns year 1 BC), and YY is not an "
    "equivalent: it pivots at 69/70, Oracle's RR at 49/50",
    "authid_clause": "Remove the clause from the source before converting (otherwise the whole "
    "routine is dropped) and add SECURITY DEFINER or SECURITY INVOKER to the generated function",
    "pragma_exception_init": "Map each ORA number onto the real PostgreSQL code and replace the "
    "substituted '50001' with it (for instance unique_violation instead of -1)",
    "subtype_range": "Replace RANGE lo .. hi with a check: CREATE DOMAIN ... CHECK (VALUE "
    "BETWEEN lo AND hi)",
    "alt_quote_literal": "Replace with PostgreSQL dollar quoting ($q$...$q$) or with an "
    "ordinary literal using doubled apostrophes",
    "goto_statement": "Rewrite with control structures: a backward jump becomes LOOP/CONTINUE, "
    "a forward jump becomes IF/ELSE or a nested block with EXIT",
    "cursor_rowtype": "Declare the variable as RECORD — in PL/pgSQL it accepts a row from any "
    "cursor, and FETCH works unchanged",
    "wm_concat": "Replace with string_agg(col, ',' ORDER BY col) — make the order explicit, "
    "since WM_CONCAT never guaranteed one",
    "read_only_view": "Restore the write ban explicitly: REVOKE INSERT, UPDATE, DELETE ON "
    "<view>, or an INSTEAD OF trigger that raises an exception",
    "sdo_geometry": "Add CREATE EXTENSION postgis before loading the schema (ora2pg does not "
    "emit it) and check the value migration itself separately",
    "mysql_enum_type": "Insert the missing CREATE TYPE <table>_<column>_t AS ENUM (...) before "
    "CREATE TABLE -- the values are already visible in the source ENUM(...)",
    "mysql_on_update_current_timestamp": "Move it to a BEFORE UPDATE trigger that sets "
    "NEW.<column> = now()",
    "mysql_on_duplicate_key_update": "Rewrite as INSERT ... ON CONFLICT (<unique key>) DO "
    "UPDATE SET ...",
    "mysql_signal": "Rewrite as RAISE EXCEPTION ... USING ERRCODE = '<sqlstate>', MESSAGE = "
    "'<text>'",
    "mysql_fulltext_index": "Rebuild it by hand: CREATE INDEX ... USING gin (to_tsvector('...', "
    "...)) after CREATE TABLE -- the columns are visible in the source FULLTEXT KEY (...)",
    'mysql_key_index': 'Rewrite as CREATE INDEX <name> ON <table> (<columns>) after CREATE TABLE -- ora2pg carries the INDEX synonym over correctly, only the KEY spelling breaks',
    'mysql_spatial_index': 'Rebuild as CREATE INDEX ... USING gist (<column>) over a PostGIS type, and check the column type itself separately',
    'mysql_limit_comma': 'Rewrite as LIMIT <count> OFFSET <offset> -- the argument order is reversed, so mechanically swapping the comma returns a different page',
    'mysql_replace_into': 'Rewrite as INSERT ... ON CONFLICT DO UPDATE, checking the difference: REPLACE deletes the row and therefore fires ON DELETE cascades',
    'mysql_insert_ignore': 'Rewrite as INSERT ... ON CONFLICT DO NOTHING, after working out which errors were actually being swallowed -- IGNORE is broader',
    'mysql_prepare_from': "Rewrite as EXECUTE <string> USING ... in PL/pgSQL -- PostgreSQL's own PREPARE ... AS does not fit here",
    'mysql_last_insert_id': 'Rewrite as INSERT ... RETURNING <column> INTO <variable>; lastval() refers to the last sequence used at all, not to a table',
    'mysql_auto_increment_start': "After loading the data, set the counter: SELECT setval(pg_get_serial_sequence('<table>','<column>'), (SELECT max(<column>) FROM <table>))",
    'mysql_date_format': "Rewrite as to_char(<date>, 'YYYY-MM-DD HH24:MI:SS') and check every specifier -- there is no error, it just silently returns the wrong thing",
    'mysql_foreign_key': 'Restore by hand: ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY ... REFERENCES ... once all the tables are loaded',
    'mysql_zero_date': "Migrate '0000-00-00' to NULL rather than to the 1970-01-01 ora2pg substitutes; check the data itself as well, not just the DEFAULT",
    'mysql_declare_handler': 'Restore the error handling with a BEGIN ... EXCEPTION WHEN ... END block; for NOT FOUND use a FOUND check rather than an EXCEPTION',
    'mysql_collate': 'Bring the comparison rule back explicitly: COLLATE with an ICU rule, the citext type, or lower() on both sides of the comparison',
    'mysql_set_type': 'Add a CHECK constraint on the allowed values (or move them into a link table) -- ora2pg leaves plain text with no validation at all',
    'mssql_bracket_identifier': 'Strip the square brackets from names in the script before converting (or export through a live SQL Server connection, where ora2pg removes them itself)',
    'mssql_newid_default': 'Add CREATE EXTENSION IF NOT EXISTS "uuid-ossp" before loading the schema, or switch to the built-in gen_random_uuid()',
    'mssql_update_set': 'Restore ordinary SQL: UPDATE <table> SET <column> = <value> -- ora2pg turns the SET into a := assignment and breaks every UPDATE',
    'mssql_identity_column': 'Replace with GENERATED BY DEFAULT AS IDENTITY (or serial) and set the counter from the maximum of the migrated data',
    'mssql_parameterless_procedure': 'Delete the empty DECLARE block with its lone semicolon from the generated code',
    'mssql_if_statement': "Rewrite in PL/pgSQL's full form: IF <condition> THEN <statements>; END IF;",
    'mssql_raiserror': "Rewrite as RAISE EXCEPTION ... USING ERRCODE = '<sqlstate>'; RAISERROR's severity is a message level, not an error code",
    'mssql_try_catch': 'Rewrite as BEGIN ... EXCEPTION WHEN OTHERS THEN ... END; ERROR_MESSAGE() becomes SQLERRM, ERROR_NUMBER() becomes SQLSTATE',
    'mssql_top_clause': 'Rewrite as LIMIT <n>; with TOP and no ORDER BY the row order stays just as undefined, so make it explicit',
    'mssql_scope_identity': 'Rewrite as INSERT ... RETURNING <column> INTO <variable> -- and check the IDENTITY itself survived (GAP-090)',
    'mssql_output_clause': 'Rewrite as RETURNING <column>; note that RETURNING does not distinguish INSERTED from DELETED',
    'mssql_iif': 'Rewrite as CASE WHEN <condition> THEN ... ELSE ... END',
    'mssql_datediff': 'Rewrite with date subtraction/EXTRACT(EPOCH ...); remember DATEDIFF counts boundaries crossed, not whole intervals',
    'mssql_charindex': "Remove the extra quotes from the generated position(''x'' in ...) -- it should read position('x' in ...)",
    'mssql_filtered_index': 'Carry the statement over as-is after the schema loads: PostgreSQL has partial indexes with WHERE and the same syntax',
    'mssql_foreign_key': 'Restore by hand: ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY ... REFERENCES ... once all the tables are loaded',
    'mssql_collation': 'Replace citext with text plus an explicit COLLATE of the right sensitivity -- for a _CS_ rule, citext inverts the meaning',
    'mssql_computed_column': 'Give the column the type its expression actually computes, or better, move it to GENERATED ALWAYS AS (...) STORED',
    'mssql_rowversion': 'Restore self-updating with a BEFORE UPDATE trigger, or switch to the system xmin column -- otherwise optimistic locking silently stops working',
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
