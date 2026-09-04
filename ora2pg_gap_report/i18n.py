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
    "scan_internal_error": {
        "ru": "[red]Внутренняя ошибка при сканировании {path}: {exc_type}: {exc}[/red] — "
        "этот файл пропущен, сканирование остальных продолжено",
        "en": "[red]Internal error scanning {path}: {exc_type}: {exc}[/red] — "
        "this file was skipped, scanning the rest continued",
    },
    "scan_detector_errors": {
        "ru": "[red]Ошибка в детекторе(ах) {names} при сканировании {path}: "
        "{exc_type}: {exc}[/red] — находки этих детекторов для файла пропущены, "
        "остальные детекторы и остальные файлы обработаны как обычно",
        "en": "[red]Detector(s) {names} failed scanning {path}: {exc_type}: "
        "{exc}[/red] — their findings for this file were skipped, every other "
        "detector and every other file were still processed normally",
    },
    "internal_error_summary": {
        "ru": "[red]Один или несколько файлов не удалось просканировать из-за внутренней "
        "ошибки (см. выше) — отчёт по остальным файлам всё равно построен, но неполон.[/red]",
        "en": "[red]One or more files couldn't be scanned due to an internal error (see "
        "above) — the report for the rest was still produced, but is incomplete.[/red]",
    },
    "unexpected_internal_error": {
        "ru": "[red]Непредвиденная внутренняя ошибка: {exc_type}: {exc}[/red] — это баг "
        "инструмента, а не найденная проблема миграции. Пожалуйста, сообщите о нём: "
        "https://github.com/Lunch418/ora2pg-gap-report/issues",
        "en": "[red]Unexpected internal error: {exc_type}: {exc}[/red] — this is a bug in "
        "the tool itself, not a migration finding. Please report it: "
        "https://github.com/Lunch418/ora2pg-gap-report/issues",
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
    "verify_new_panel_title": {
        "ru": "Появилось после миграции (не было в baseline)",
        "en": "New in the generated output (not in the baseline)",
    },
    "verify_new_col_count": {"ru": "Находок", "en": "Findings"},
    "verify_new_footer_note": {
        "ru": "Эти детекторы сработали на сгенерированном выводе, но в baseline их нет: "
        "конструкции не было в исходнике Oracle — её внесла сама конверсия. Сравнивать "
        "«до/после» тут не с чем, поэтому колонки «До» нет.",
        "en": "These detectors fired on the generated output but aren't in the baseline: "
        "the construct wasn't in the Oracle source — the conversion itself introduced it. "
        "There's no before/after to compare, which is why there's no \"Before\" column.",
    },
    "verify_summary_new_in_output": {
        "ru": "Появилось после миграции",
        "en": "New in output",
    },
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
    "verify_unknown_detectors": {
        "ru": "В baseline есть детекторы, которых нет в этой сборке: {detectors}. "
        "Снапшот, похоже, сделан другой версией инструмента — обновите её или "
        "пересоздайте baseline; сверять по части находок было бы враньём.",
        "en": "The baseline contains detectors this build does not have: {detectors}. "
        "The snapshot looks like it came from a different version -- update it or "
        "re-create the baseline; verifying against part of it would be misleading.",
    },
    "verify_mixed_dialects": {
        "ru": "В baseline смешаны находки нескольких диалектов ({dialects}). Один прогон "
        "сканирует один диалект, так что такой снапшот собран вручную — разделите его "
        "и сверяйте каждый диалект отдельно.",
        "en": "The baseline mixes findings from several dialects ({dialects}). One scan "
        "covers one dialect, so this snapshot was assembled by hand -- split it and "
        "verify each dialect separately.",
    },
    "verify_dialect_mismatch": {
        "ru": "Запрошен --dialect {requested}, а baseline сделан для диалекта "
        "{baseline_dialect}. Сверка чужими детекторами показала бы «не найдено» по всем "
        "находкам — это была бы не проверка, а тавтология.",
        "en": "--dialect {requested} was requested, but the baseline was taken with "
        "{baseline_dialect}. Verifying with another dialect's detectors would report "
        "\"not detected\" for every finding -- a tautology, not a check.",
    },
    "connect_by_oracle_only": {
        "ru": "--check-connect-by работает только с --dialect oracle (сейчас {dialect}): "
        "CONNECT BY — конструкция Oracle, и сама проверка запускает ora2pg в "
        "Oracle-режиме. На файле другого диалекта она не нашла бы ничего никогда.",
        "en": "--check-connect-by only works with --dialect oracle (got {dialect}): "
        "CONNECT BY is Oracle-only syntax, and the check itself runs ora2pg in Oracle "
        "mode. On another dialect's file it could never find anything.",
    },
    "fix_no_fixers_for_dialect": {
        "ru": "Для диалекта {dialect} механических автофиксов нет. Это не пробел в "
        "реализации: у его подтверждённых gap'ов правка требует решения (какой именно "
        "конструкцией заменить) либо данных, которых в сгенерированном файле уже нет.",
        "en": "There are no mechanical autofixes for the {dialect} dialect. That is not a "
        "gap in the implementation: fixing its confirmed gaps needs a decision (what to "
        "replace the construct with) or data the generated file no longer carries.",
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
    "tui_warning_detector_error": {
        "ru": "Ошибка в детекторе(ах) {names} на файле {path}: {exc_type}: {exc} — "
        "их находки для этого файла пропущены",
        "en": "Detector(s) {names} failed on {path}: {exc_type}: {exc} — "
        "their findings for this file were skipped",
    },
    "tui_warning_scan_error": {
        "ru": "Внутренняя ошибка при сканировании {path}: {exc_type}: {exc} — файл пропущен",
        "en": "Internal error scanning {path}: {exc_type}: {exc} — file skipped",
    },
    "tui_worker_crashed": {
        "ru": "Внутренняя ошибка: {exc_type}: {exc}. Это баг инструмента — сообщите о нём: "
        "https://github.com/Lunch418/ora2pg-gap-report/issues",
        "en": "Internal error: {exc_type}: {exc}. This is a bug in the tool — please report it: "
        "https://github.com/Lunch418/ora2pg-gap-report/issues",
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


