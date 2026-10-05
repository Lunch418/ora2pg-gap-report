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
import sys
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


def peek_language(argv: list[str] | None) -> str | None:
    """--lang's value read straight off argv, before argparse runs.

    Both entry points need this and for the same reason: their own --help
    text is localized, so the language has to be known before the parser
    that would parse --lang exists. Accepts every spelling argparse does
    for this option -- `-l en`, `--lang en`, `--lang=en`, `-len` -- since
    a short flag that worked everywhere except for choosing the help
    language would be worse than not having one.

    Deliberately forgiving rather than a second parser: anything it
    doesn't recognise falls through to resolve_language()'s normal
    precedence, and argparse still validates the real value once actual
    parsing happens.
    """
    raw = list(argv) if argv is not None else sys.argv[1:]
    for i, arg in enumerate(raw):
        if arg in ("--lang", "-l") and i + 1 < len(raw) and raw[i + 1] in _LANGUAGES:
            return raw[i + 1]
        for prefix in ("--lang=", "-l"):
            if arg.startswith(prefix) and arg[len(prefix) :] in _LANGUAGES:
                return arg[len(prefix) :]
    return None


# A string with the Cyrillic that every Russian UI string is made of. Used
# to ask a stream's encoder "could you print this?" without printing it.
_RUSSIAN_PROBE = "Русский"


def stream_can_encode(text: str, stream: object | None = None) -> bool:
    """Whether `stream`'s encoding can represent `text`.

    Windows consoles default to a legacy code page (cp1252 on a Western
    install), which has no Cyrillic at all. Writing Russian to one raises
    UnicodeEncodeError from deep inside whatever is doing the printing --
    for argparse's --help that surfaced as the CLI's top-level handler
    reporting an "unexpected internal error" and exiting 3, with an empty
    stdout, on the very first command a Windows user would run.

    Defaults to sys.stdout, and answers True when there is nothing to ask
    (no stream, no encoding attribute, a stream that has been replaced by
    a test harness): the caller's job is to avoid a crash it can foresee,
    not to second-guess an environment it cannot inspect.
    """
    if stream is None:
        stream = sys.stdout
    encoding = getattr(stream, "encoding", None)
    if not encoding:
        return True
    try:
        text.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


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

    # Russian remains the silent default -- except on a console that
    # cannot encode it, where printing it does not produce worse output,
    # it raises. Nobody asked for Russian in this branch (that is what
    # every branch above is for), so English, which every encoding this
    # could be represents, is the better answer than a crash. An explicit
    # choice above is honoured either way: a user who asks for Russian
    # gets Russian.
    return "ru" if stream_can_encode(_RUSSIAN_PROBE) else "en"


# Nouns the reports count, in every form each language needs: Russian
# picks one of three by the number (1 находка, 2 находки, 5 находок),
# English one of two. Kept apart from _UI, whose entries are single
# templates.
_COUNTED: dict[str, dict[str, tuple[str, ...]]] = {
    "finding": {"ru": ("находка", "находки", "находок"), "en": ("finding", "findings")},
    "gap": {"ru": ("тип пробела", "типа пробелов", "типов пробелов"), "en": ("kind of gap", "kinds of gap")},
    "object": {"ru": ("объект", "объекта", "объектов"), "en": ("object", "objects")},
    "file": {"ru": ("файл", "файла", "файлов"), "en": ("file", "files")},
    "hour": {"ru": ("час", "часа", "часов"), "en": ("hour", "hours")},
    "statement": {"ru": ("команда", "команды", "команд"), "en": ("statement", "statements")},
    "error": {"ru": ("ошибка", "ошибки", "ошибок"), "en": ("error", "errors")},
}


def number(lang: str, value: float) -> str:
    """`value` without trailing zeros, with the decimal mark the language
    uses: number("ru", 53.5) -> "53,5", number("en", 53.5) -> "53.5"."""
    text = f"{value:g}"
    return text.replace(".", ",") if lang != "en" else text


def count(lang: str, noun: str, n: int) -> str:
    """`n` with `noun` in the grammatical form the number takes:
    count("ru", "finding", 21) -> "21 находка", count("en", "file", 1)
    -> "1 file"."""
    forms = _COUNTED[noun]["en" if lang == "en" else "ru"]
    if lang == "en":
        return f"{n} {forms[0] if n == 1 else forms[1]}"
    last_two, last = n % 100, n % 10
    if last == 1 and last_two != 11:
        form = forms[0]
    elif 2 <= last <= 4 and not 12 <= last_two <= 14:
        form = forms[1]
    else:
        form = forms[2]
    return f"{n} {form}"


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
    "col_file": {"ru": "Файл", "en": "File"},
    "col_object": {"ru": "Объект", "en": "Object"},
    "col_line": {"ru": "Строка", "en": "Line"},
    "col_severity": {"ru": "Severity", "en": "Severity"},
    "col_detector": {"ru": "Детектор", "en": "Detector"},
    "effort_panel_title": {"ru": "Оценка ручной доработки", "en": "Manual rework estimate"},
    "next_steps_heading": {"ru": "Дальше", "en": "Next"},
    "next_step_checklist": {
        "ru": "список работ, который помнит отметки",
        "en": "a task list that remembers what is done",
    },
    "next_step_prepare": {
        "ru": "до ora2pg: подготовить исходный дамп",
        "en": "before ora2pg: prepare the source dump",
    },
    "next_step_fix": {
        "ru": "после ora2pg: механические исправления",
        "en": "after ora2pg: the mechanical fixes",
    },
    "next_step_load_check": {
        "ru": "проверка на настоящем PostgreSQL",
        "en": "check it against a real PostgreSQL",
    },
    "footer_hint_severity_label": {
        "ru": "Показать только высокую критичность:",
        "en": "Show only high severity:",
    },
    "footer_hint_object_label": {
        "ru": "Сфокусироваться на одном объекте:    ",
        "en": "Focus on a single object:            ",
    },
    "baseline_panel_title": {"ru": "Сравнение с baseline", "en": "Baseline comparison"},
    "new_findings_label": {"ru": "Новые находки:\n", "en": "New findings:\n"},
    # cli.py runtime messages
    "explain_unknown_gap": {
        "ru": "[red]Неизвестный GAP: {ref}[/red] — ожидается номер из "
        "docs/research/GAP_REGISTRY.md, например GAP-023 или 023",
        "en": "[red]Unknown GAP: {ref}[/red] — expected a number from "
        "docs/research/GAP_REGISTRY.md, e.g. GAP-023 or 023",
    },
    # --- ora2pg-gap-export ------------------------------------------
    # The export command had no --lang at all, so every string it printed
    # was Russian regardless of the language the user had chosen for the
    # rest of the tool.
    "export_description": {
        "ru": "Выгружает DDL объектов живой Oracle-схемы в отдельные .sql "
        "файлы — для последующего анализа через `ora2pg-gap-report`.",
        "en": "Exports a live Oracle schema's object DDL to individual .sql "
        "files, for offline analysis with `ora2pg-gap-report`.",
    },
    "export_help_dsn": {
        "ru": "Oracle connect string, напр. host:1521/ORCLPDB1",
        "en": "Oracle connect string, e.g. host:1521/ORCLPDB1",
    },
    "export_help_owner": {
        "ru": "Схема, из которой выгружать объекты (по умолчанию — совпадает с --user)",
        "en": "Schema to export objects from (defaults to --user)",
    },
    "export_help_types": {
        "ru": "Какие типы объектов выгружать, через запятую (по умолчанию все: "
        "{choices}). Имена — как в ALL_OBJECTS.object_type, регистр не важен",
        "en": "Which object types to export, comma separated (default: all of "
        "{choices}). Names are as in ALL_OBJECTS.object_type; case doesn't matter",
    },
    "export_help_output_dir": {
        "ru": "Куда сохранить .sql файлы (по умолчанию — ./oracle_export)",
        "en": "Where to write the .sql files (default: ./oracle_export)",
    },
    "export_unknown_type": {
        "ru": "неизвестный тип объекта: {unknown}. Доступны: {choices}",
        "en": "unknown object type: {unknown}. Available: {choices}",
    },
    "export_connect_failed": {
        "ru": "Не удалось подключиться к Oracle: {exc}",
        "en": "Could not connect to Oracle: {exc}",
    },
    "export_failed": {
        "ru": "Ошибка при выгрузке схемы: {exc}",
        "en": "Schema export failed: {exc}",
    },
    "export_done": {
        "ru": "Экспортировано {n} объект(ов) в {dir}/",
        "en": "Exported {n} object(s) to {dir}/",
    },
    "export_partial": {
        "ru": "Не удалось выгрузить {n} объект(ов):",
        "en": "Could not export {n} object(s):",
    },
    "export_password_prompt": {
        "ru": "Пароль Oracle: ",
        "en": "Oracle password: ",
    },
    "oracledb_missing": {
        "ru": "python-oracledb не установлен. Установите: "
        "pip install ora2pg-gap-report[oracle]",
        "en": "python-oracledb is not installed. Install it with: "
        "pip install ora2pg-gap-report[oracle]",
    },
    "ora2pg_not_runnable": {
        "ru": "исполняемый файл ora2pg не найден или не запускается "
        "({bin}: {exc}) — см. README по установке",
        "en": "the ora2pg executable was not found or could not be run "
        "({bin}: {exc}) — see the README for setup",
    },
    "ora2pg_timeout": {
        "ru": "ora2pg не ответил за {timeout}с",
        "en": "ora2pg did not respond within {timeout}s",
    },
    "ora2pg_failed": {
        "ru": "ora2pg завершился с кодом {code}:\n{detail}",
        "en": "ora2pg exited with code {code}:\n{detail}",
    },
    "explain_doc_not_translated": {
        "ru": "[dim](документ ниже — на английском: русский перевод этого "
        "gap'а ещё не готов)[/dim]",
        "en": "[dim](the document below is in Russian: its English "
        "translation is not ready yet)[/dim]",
    },
    "confirmed_versions": {
        "ru": "Подтверждено {last_verified} на: ora2pg {ora2pg_version}, "
        "PostgreSQL {postgresql_version}",
        "en": "Confirmed {last_verified} on: ora2pg {ora2pg_version}, "
        "PostgreSQL {postgresql_version}",
    },
    "ora2pg_version_mismatch": {
        "ru": "Установлен ora2pg {installed}, а находки подтверждались на "
        "{verified}. Поведение ora2pg на вашей версии может отличаться — "
        "проверьте docs/research/GAP_REGISTRY.md.",
        "en": "Installed ora2pg is {installed}, but the findings were confirmed "
        "against {verified}. ora2pg may behave differently on your version — "
        "see docs/research/GAP_REGISTRY.md.",
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
        "--check-connect-by, --verify, --fix, --write, --load-check, --format, --output, "
        "--severity или --object[/red]",
        "en": "[red]--explain is a standalone documentation lookup, not a scan: it can't be "
        "combined with file paths, --fail-on, --save, --baseline, --check-connect-by, "
        "--verify, --fix, --write, --load-check, --format, --output, --severity, or --object[/red]",
    },
    "tui_conflict_error": {
        "ru": "[red]--tui — самостоятельный интерактивный режим: принимает не больше одного "
        "пути (стартовая точка в дереве) и не сочетается с --explain, --verify, --fix, --load-check, "
        "--write, --fail-on, --save, --baseline, --check-connect-by, --severity, --object, "
        "--format или --output[/red]",
        "en": "[red]--tui is a standalone interactive mode: it takes at most one path (a "
        "starting point for the tree) and can't be combined with --explain, --verify, "
        "--fix, --load-check, --write, --fail-on, --save, --baseline, --check-connect-by, --severity, "
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
        "ru": "[red]--write работает только вместе с --fix или --prepare[/red]",
        "en": "[red]--write only makes sense together with --fix or --prepare[/red]",
    },
    "prepare_fix_conflict_error": {
        "ru": "[red]--prepare правит исходный дамп до ora2pg, --fix - вывод ora2pg после; "
        "это разные файлы, запускайте их по отдельности[/red]",
        "en": "[red]--prepare edits the source dump before ora2pg, --fix edits ora2pg's output "
        "after it; they are different files, run them separately[/red]",
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
    # --load-check (loading the generated output into a real PostgreSQL, see load_check.py)
    "load_check_conflict_error": {
        "ru": "[red]--load-check - отдельный режим, его нельзя сочетать с --explain, --verify, "
        "--fix, --write, --tui, --fail-on, --save, --baseline, --check-connect-by, --severity "
        "или --object[/red]",
        "en": "[red]--load-check is a standalone mode, it can't be combined with --explain, "
        "--verify, --fix, --write, --tui, --fail-on, --save, --baseline, --check-connect-by, "
        "--severity, or --object[/red]",
    },
    "load_check_unsupported_format": {
        "ru": "[red]--load-check поддерживает только --format terminal и --format json[/red]",
        "en": "[red]--load-check only supports --format terminal and --format json[/red]",
    },
    "load_check_dsn_notice": {
        "ru": "[dim]Загрузка в {target}: всё выполняется в одной транзакции и откатывается в конце, "
        "но DDL держит блокировки до отката - используйте пустую тестовую базу, не рабочую.[/dim]",
        "en": "[dim]Loading into {target}: everything runs in one transaction that is rolled back "
        "at the end, but DDL holds its locks until then - use an empty scratch database, not a "
        "live one.[/dim]",
    },
    "load_check_starting_docker": {
        "ru": "Запуск одноразового PostgreSQL ({image}) в docker...",
        "en": "Starting a throwaway PostgreSQL ({image}) in docker...",
    },
    "load_check_running": {
        "ru": "Загрузка {files} в PostgreSQL...",
        "en": "Loading {files} into PostgreSQL...",
    },
    "load_check_no_psql": {
        "ru": "[red]Не найден psql ({psql}). Установите клиент PostgreSQL или используйте "
        "--load-check docker - тогда psql не нужен.[/red]",
        "en": "[red]psql not found ({psql}). Install the PostgreSQL client, or use "
        "--load-check docker, which doesn't need it.[/red]",
    },
    "load_check_no_docker": {
        "ru": "[red]Не найден docker ({docker}). Установите docker или передайте строку "
        "подключения к тестовой базе: --load-check postgresql://user@host/scratch[/red]",
        "en": "[red]docker not found ({docker}). Install docker, or pass a connection string "
        "to a scratch database: --load-check postgresql://user@host/scratch[/red]",
    },
    "load_check_docker_failed": {
        "ru": "[red]Не удалось запустить контейнер {image}:[/red]\n{detail}",
        "en": "[red]Couldn't start the {image} container:[/red]\n{detail}",
    },
    "load_check_docker_not_ready": {
        "ru": "[red]PostgreSQL в контейнере {image} не запустился за отведённое время. "
        "Последние строки журнала:[/red]\n{detail}",
        "en": "[red]PostgreSQL in the {image} container didn't come up in time. The last "
        "lines of its log:[/red]\n{detail}",
    },
    "load_check_connect_failed": {
        "ru": "[red]psql не смог подключиться к серверу:[/red]\n{detail}",
        "en": "[red]psql couldn't connect to the server:[/red]\n{detail}",
    },
    "load_check_incomplete": {
        "ru": "[red]psql остановился, не дойдя до конца файлов (оборвалось соединение?). "
        "Результат неполный, поэтому не показан. Последний вывод psql:[/red]\n{detail}",
        "en": "[red]psql stopped before reaching the end of the files (a dropped connection?). "
        "The result is incomplete, so it isn't shown. psql's last output:[/red]\n{detail}",
    },
    "load_check_heading": {
        "ru": "Проверка загрузкой в PostgreSQL",
        "en": "Load check against PostgreSQL",
    },
    "load_check_panel_title": {"ru": "Итог", "en": "Summary"},
    "load_check_server": {"ru": "Сервер", "en": "Server"},
    "load_check_loaded": {"ru": "Загружено", "en": "Loaded"},
    "load_check_loaded_value": {
        "ru": "{files}, {statements}",
        "en": "{files}, {statements}",
    },
    "load_check_failed_label": {"ru": "Не загрузилось", "en": "Didn't load"},
    "load_check_cat_fixable": {"ru": "исправит --fix", "en": "--fix repairs it"},
    "load_check_cat_gap": {"ru": "известный пробел", "en": "a known gap"},
    "load_check_cat_unknown": {"ru": "нет в реестре", "en": "not in the registry"},
    "load_check_cat_dependency": {"ru": "нет нужного объекта", "en": "a missing object"},
    "load_check_cat_environment": {"ru": "не проверить здесь", "en": "can't be checked here"},
    "load_check_section_fixable": {
        "ru": "Исправит --fix",
        "en": "--fix repairs these",
    },
    "load_check_section_gap": {
        "ru": "Известные пробелы ora2pg",
        "en": "Known ora2pg gaps",
    },
    "load_check_section_unknown": {
        "ru": "Ошибки, которых нет в реестре",
        "en": "Errors the registry doesn't know",
    },
    "load_check_section_dependency": {
        "ru": "Ссылаются на объект, которого нет",
        "en": "Refer to an object that doesn't exist",
    },
    "load_check_section_environment": {
        "ru": "Не проверить внутри проверки",
        "en": "Can't be checked inside the check",
    },
    "load_check_hint_fixable": {
        "ru": "ora2pg-gap-report --fix --write {file}",
        "en": "ora2pg-gap-report --fix --write {file}",
    },
    "load_check_hint_gap": {
        "ru": "Что делать: ora2pg-gap-report --explain GAP-{number}",
        "en": "What to do: ora2pg-gap-report --explain GAP-{number}",
    },
    "load_check_hint_detector": {
        "ru": "Детектор: {detector}",
        "en": "Detector: {detector}",
    },
    "load_check_note_unknown": {
        "ru": "Этих ошибок нет в реестре пробелов. Если это ошибка конверсии ora2pg, а не "
        "исходной схемы, расскажите о ней: https://github.com/Lunch418/ora2pg-gap-report/issues/2",
        "en": "The gap registry doesn't know these errors. If one is ora2pg's conversion going "
        "wrong rather than the source schema, please report it: "
        "https://github.com/Lunch418/ora2pg-gap-report/issues/2",
    },
    "load_check_note_dependency": {
        "ru": "Обычно это эхо ошибки выше (не создалась таблица или тип) или объект, который "
        "лежит вне загруженных файлов. Сначала исправьте ошибки из разделов выше.",
        "en": "Usually the echo of an error above (a table or type that failed to create) or "
        "an object that lives outside the loaded files. Fix the sections above first.",
    },
    "load_check_note_environment": {
        "ru": "Это не ошибка миграции: команда не может выполниться внутри транзакции проверки "
        "(CREATE INDEX CONCURRENTLY, COMMIT внутри DO), сервер отказал в правах или нет "
        "расширения, либо сработал тайм-аут. Такие команды не проверены.",
        "en": "Not a migration error: the statement can't run inside the check's transaction "
        "(CREATE INDEX CONCURRENTLY, a COMMIT inside DO), the server refused the privilege or "
        "lacks an extension, or a timeout fired. These statements weren't checked.",
    },
    "load_check_more": {
        "ru": "... и ещё {errors} - полный список: --format json",
        "en": "... and {errors} more - the full list: --format json",
    },
    "load_check_clean": {
        "ru": "Всё загрузилось: {statements} из {files}, ни одной ошибки.",
        "en": "Everything loaded: {statements} from {files}, not a single error.",
    },
    "load_check_nothing_loaded": {
        "ru": "Ни один файл не удалось загрузить - причины ниже.",
        "en": "No file could be loaded - the reasons are below.",
    },
    "load_check_neutralised": {
        "ru": "Не выполнялось (иначе проверка была бы неверной): {items}",
        "en": "Not run (the check would be wrong otherwise): {items}",
    },
    "load_check_neutralised_meta": {"ru": "команды psql - {n}", "en": "psql commands - {n}"},
    "load_check_neutralised_transaction": {
        "ru": "управление транзакцией - {n}",
        "en": "transaction control - {n}",
    },
    "load_check_neutralised_setting": {
        "ru": "SET check_function_bodies - {n}",
        "en": "SET check_function_bodies - {n}",
    },
    "load_check_include_skipped": {
        "ru": "[yellow]{file}:{line}: {command} не выполнялся - передайте подключаемые файлы "
        "или их каталог в --load-check вместе с этим.[/yellow]",
        "en": "[yellow]{file}:{line}: {command} wasn't run - pass the included files, or their "
        "directory, to --load-check along with this one.[/yellow]",
    },
    "load_check_skipped_unreadable": {
        "ru": "[yellow]{file}: не прочитан ({detail}), не загружался.[/yellow]",
        "en": "[yellow]{file}: couldn't be read ({detail}), not loaded.[/yellow]",
    },
    "load_check_skipped_unterminated": {
        "ru": "[yellow]{file}: файл заканчивается внутри незакрытой кавычки или комментария "
        "(начало на строке {line}), не загружался - psql склеил бы его со следующим файлом.[/yellow]",
        "en": "[yellow]{file}: the file ends inside an unclosed quote or comment (opened on line "
        "{line}), not loaded - psql would glue it to the next file.[/yellow]",
    },
    "load_check_footer": {
        "ru": "Всё выполнялось в одной транзакции и откачено - в базе ничего не осталось. "
        "Тела PL/pgSQL проверены компилятором (check_function_bodies = on), но ничего не "
        "запускалось: то, что загрузилось, может вести себя иначе, чем в Oracle.",
        "en": "Everything ran in one transaction that was rolled back - nothing was left in the "
        "database. PL/pgSQL bodies were compiled (check_function_bodies = on), but nothing was "
        "executed: what loaded may still behave differently from Oracle.",
    },
    "load_check_failed_summary": {
        "ru": "\n[bold red]Сгенерированный код не загружается[/bold red] - {errors}.",
        "en": "\n[bold red]The generated code doesn't load[/bold red] - {errors}.",
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
        "ru": "| Файл | Объект | Строка | Серьёзность | Фрагмент | Что не так | GAP | Когда ломается |",
        "en": "| File | Object | Line | Severity | Snippet | Problem | GAP | Fails at |",
    },
    "md_explanations_heading": {
        "ru": "\n## Пояснения\n\n",
        "en": "\n## Explanations\n\n",
    },
    # The terminal report (terminal_report.render), beside the report_*
    # strings it shares with the HTML report.
    "nothing_scanned": {
        "ru": "Ни один из указанных путей не удалось просканировать — отчёт не создан. Причины выше.",
        "en": "None of the given paths could be scanned, so no report was made. The reasons are above.",
    },
    "term_scanned": {"ru": "Просканировано: {objects}", "en": "Scanned: {objects}"},
    "term_elapsed": {"ru": " за {s:.1f} с", "en": " in {s:.1f} s"},
    "term_effort_patterns": {
        "ru": "{gaps} на {findings}: каждый тип оценён полностью один раз, повторы — как применение "
        "уже найденного исправления",
        "en": "{gaps} across {findings}: each kind is priced in full once, repeats as applying a fix "
        "already worked out",
    },
    "term_more_findings": {
        "ru": "… и ещё {findings} — полный список: ora2pg-gap-report ... -f html -o report.html",
        "en": "… and {findings} more — the full list: ora2pg-gap-report ... -f html -o report.html",
    },
    "term_more_objects": {"ru": "… и ещё {objects}", "en": "… and {objects} more"},
    "term_details_heading": {"ru": "Подробно", "en": "In detail"},
    "term_verify_heading": {
        "ru": "Что из найденного до миграции осталось в сгенерированном коде",
        "en": "What the pre-migration findings left in the generated code",
    },
    # The HTML report (html_report.py).
    "report_heading": {
        "ru": "{source} -> PostgreSQL: где сломается перенос",
        "en": "{source} -> PostgreSQL: where the migration breaks",
    },
    "report_scanned": {"ru": "Просканировано: {files}, {objects}.", "en": "Scanned: {files}, {objects}."},
    "report_found": {"ru": "Найдено: {findings}, {gaps}.", "en": "Found: {findings}, {gaps}."},
    "report_rail_label": {"ru": "Когда ломается", "en": "When it breaks"},
    "stage_conversion_name": {"ru": "Конвертация", "en": "Conversion"},
    "stage_conversion_desc": {"ru": "объект теряется ещё в ora2pg", "en": "the object is lost inside ora2pg"},
    "stage_deployment_name": {"ru": "Загрузка схемы", "en": "Schema load"},
    "stage_deployment_desc": {"ru": "сгенерированный DDL не загружается", "en": "the generated DDL fails to load"},
    "stage_runtime_name": {"ru": "Выполнение", "en": "Run time"},
    "stage_runtime_desc": {"ru": "код падает при первом вызове", "en": "the code fails on its first call"},
    "stage_semantic_name": {"ru": "Молча", "en": "Silently"},
    "stage_semantic_desc": {"ru": "ошибки нет, меняется поведение", "en": "no error, the behaviour changes"},
    "stage_none_name": {"ru": "Без стадии", "en": "No stage"},
    "stage_none_desc": {
        "ru": "недооценка трудоёмкости и вызовы, которые стоит проверить",
        "en": "underestimated cost, and calls worth checking",
    },
    "report_filter_severity": {"ru": "Критичность", "en": "Severity"},
    "report_filter_stage": {"ru": "Стадия", "en": "Stage"},
    "report_filter_all": {"ru": "Все", "en": "All"},
    "report_gap_why": {"ru": "Почему", "en": "Why"},
    "report_gap_fix": {"ru": "Что делать", "en": "What to do"},
    "report_gap_recipe": {"ru": "Рецепт", "en": "Recipe"},
    "report_gap_prepare": {"ru": "До ora2pg", "en": "Before ora2pg"},
    # --format checklist (checklist.py)
    "checklist_title": {"ru": "Чеклист миграции {source} -> PostgreSQL", "en": "Migration checklist: {source} -> PostgreSQL"},
    "checklist_made": {
        "ru": "Создан ora2pg-gap-report {version}, обновлён {date}.",
        "en": "Made by ora2pg-gap-report {version}, updated {date}.",
    },
    "checklist_progress": {
        "ru": "Сделано: {done} из {total} ({percent} %)",
        "en": "Done: {done} of {total} ({percent} %)",
    },
    "checklist_how": {
        "ru": "Отмечайте сделанное прямо в файле (`[x]`). Повторный запуск с тем же `-o` сохранит "
        "отметки и сам отметит то, чего больше нет в просканированных файлах.",
        "en": "Tick what is done right in the file (`[x]`). Running again with the same `-o` keeps "
        "the ticks and ticks whatever the scanned files no longer contain.",
    },
    "checklist_empty": {
        "ru": "Проблемных конструкций не найдено - отмечать нечего.",
        "en": "No problematic constructs found - nothing to tick off.",
    },
    "checklist_gap_done": {"ru": "готово", "en": "done"},
    "checklist_breaks_at": {"ru": "ломается: {stage}", "en": "breaks at: {stage}"},
    "checklist_open_of": {"ru": "осталось {open} из {total}", "en": "{open} of {total} open"},
    "checklist_details": {"ru": "Подробнее", "en": "Details"},
    "checklist_line": {"ru": "(строка {lines})", "en": "(line {lines})"},
    "checklist_lines": {"ru": "(строки {lines})", "en": "(lines {lines})"},
    "checklist_gone": {"ru": "больше не найдено", "en": "no longer found"},
    "checklist_not_scanned": {"ru": "файл в этот раз не сканировался", "en": "file not scanned this time"},
    "checklist_not_ours": {
        "ru": "[red]{path} уже существует и не похож на чеклист ora2pg-gap-report - не перезаписываю. "
        "Укажите другой --output или удалите файл.[/red]",
        "en": "[red]{path} already exists and isn't an ora2pg-gap-report checklist - not overwriting "
        "it. Choose another --output, or remove the file.[/red]",
    },
    "explain_recipe_line": {
        "ru": "[bold]Рецепт:[/bold] {title} - {where}",
        "en": "[bold]Recipe:[/bold] {title} - {where}",
    },
    "report_gap_where": {"ru": "Где", "en": "Where"},
    "report_col_file": {"ru": "Файл", "en": "File"},
    "report_col_line": {"ru": "Строка", "en": "Line"},
    "report_col_object": {"ru": "Объект", "en": "Object"},
    "report_col_snippet": {"ru": "Фрагмент", "en": "Fragment"},
    "report_effort_label": {"ru": "Ручная доработка", "en": "Manual rework"},
    "report_effort_range": {"ru": "{lo}–{hi} ч", "en": "{lo}–{hi} h"},
    "report_effort_caveat": {
        "ru": "неоткалиброванная эвристика по severity, не измерение (см. README.md, «Почему почти всё high»)",
        "en": "an uncalibrated heuristic based on severity, not a measurement (see README.md, "
        "\"Why almost everything is `high`\")",
    },
    "report_top_objects": {"ru": "Где больше всего находок", "en": "Where the findings concentrate"},
    "report_gaps_heading": {"ru": "Пробелы", "en": "Gaps"},
    "report_empty_title": {"ru": "Пробелов не найдено", "en": "No gaps found"},
    "report_empty_text": {
        "ru": "Ни одна проверка не сработала на этих файлах. Это не гарантия гладкой миграции: "
        "инструмент ищет только подтверждённые пробелы ora2pg.",
        "en": "No check fired on these files. That is not a promise of a smooth migration: the "
        "tool looks only for confirmed ora2pg gaps.",
    },
    "report_footer": {
        "ru": "ora2pg-gap-report {version}. Каждый пробел подтверждён прогоном ora2pg 25.0 и PostgreSQL 16.",
        "en": "ora2pg-gap-report {version}. Every gap was confirmed with ora2pg 25.0 and PostgreSQL 16.",
    },
    # The no-findings variants. A clean scan is the ordinary outcome in
    # CI, and the counts breakdown is empty then, so the parenthesised
    # form rendered as "Находок: 0 ()".
    "markdown_findings_found_none": {
        "ru": "Находок: 0\n\n",
        "en": "Findings: 0\n\n",
    },
    "markdown_report_title": {"ru": "# Отчёт ora2pg-gap-report\n\n", "en": "# ora2pg-gap-report report\n\n"},
    "markdown_findings_found": {
        "ru": "Находок: {n} ({counts})\n\n",
        "en": "Findings: {n} ({counts})\n\n",
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
        "ru": 'Находит в схеме Oracle, дампе MySQL/MariaDB или скрипте T-SQL то, что ora2pg при переносе в PostgreSQL потеряет, сломает или перенесёт неверно, — и объясняет, почему и что делать. Каждый из {n} пробелов подтверждён прогоном настоящего ora2pg и PostgreSQL.',
        "en": 'Finds what ora2pg will lose, break or carry over wrongly when it moves an Oracle schema, a MySQL/MariaDB dump or a T-SQL script to PostgreSQL -- and explains why and what to do. Each of the {n} gaps was confirmed with a real ora2pg and PostgreSQL run.',
    },
    "help_usage": {"ru": "использование: ", "en": "usage: "},
    "help_positionals": {"ru": "аргументы", "en": "positional arguments"},
    "help_optionals": {"ru": "параметры", "en": "options"},
    "help_help": {"ru": "Показать эту справку и выйти", "en": "Show this help and exit"},
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
        "показа заказчику/руководству. checklist - Markdown-чеклист работ по объектам; при "
        "повторной генерации в тот же --output отмеченные галочки сохраняются, а то, чего "
        "больше нет в просканированных файлах, отмечается само.",
        "en": "Report format. Defaults to colored terminal output if stdout is a "
        "tty and --output isn't given; markdown otherwise. sarif — SARIF "
        "2.1.0, for GitHub/GitLab code scanning. html — a self-contained "
        "HTML page (no external resources), for showing a client/manager. "
        "checklist - a Markdown checklist of the work, per object; regenerating it "
        "into the same --output keeps the ticked boxes and ticks what the scanned "
        "files no longer contain.",
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
        "ru": 'Диалект исходного кода: oracle (по умолчанию), mysql (дампы MySQL/MariaDB, как для ora2pg -m) или mssql (скрипты T-SQL/SQL Server, как для ora2pg -M). Выбирает детекторы для сканирования и исправления для --fix; в --verify диалект берётся из baseline, а явно указанный сверяется с ним. Не сочетается с --tui (там свой выбор) и --explain.',
        "en": 'Source dialect: oracle (default), mysql (MySQL/MariaDB dumps, as for ora2pg -m) or mssql (T-SQL/SQL Server scripts, as for ora2pg -M). Picks the detectors for a scan and the fixes for --fix; --verify takes the dialect from the baseline and checks an explicit one against it. Not combinable with --tui (it has its own picker) or --explain.',
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
        "PostgreSQL-коду (не к Oracle-исходнику - как --verify, читает пути как результат "
        "миграции). Набор зависит от --dialect: для oracle - двойные скобки в GENERATED ... "
        "AS IDENTITY (GAP-028) и пропущенный RECURSIVE в рекурсивном WITH (GAP-024), для "
        "mysql - LIMIT a, b (GAP-075), для mssql - кавычки в CHARINDEX (GAP-100) и пустой "
        "DECLARE (GAP-091). По умолчанию ничего "
        "не меняет на диске, только печатает unified diff; для реальной перезаписи файлов "
        "добавьте --write. Самостоятельный режим - не сочетается с --explain/--verify/--tui/"
        "--fail-on/--save/--baseline/--check-connect-by/--severity/--object/--format/--output.",
        "en": "Apply known mechanical fixes to ora2pg's *generated* PostgreSQL code (not "
        "Oracle source -- like --verify, reads paths as post-migration output). The set "
        "depends on --dialect: for oracle, the double parens in GENERATED ... AS IDENTITY "
        "(GAP-028) and the missing RECURSIVE in a recursive WITH (GAP-024); for mysql, "
        "LIMIT a, b (GAP-075); for mssql, the CHARINDEX quotes (GAP-100) and the empty "
        "DECLARE (GAP-091). Prints a unified diff by "
        "default, without touching anything on disk; add --write to actually rewrite the "
        "files. A standalone mode -- not combinable with --explain/--verify/--tui/--fail-on/"
        "--save/--baseline/--check-connect-by/--severity/--object/--format/--output.",
    },
    "help_load_check": {
        "ru": "Загрузить сгенерированный ora2pg PostgreSQL-код в настоящий PostgreSQL и "
        "показать, какие команды не загрузились и каким пробелам (GAP-NNN) они соответствуют, "
        "какие исправит --fix, какие - эхо более ранней ошибки. TARGET: docker - одноразовый "
        "контейнер postgres:16-alpine (нужен только docker), docker:IMAGE - свой образ, или "
        "строка подключения libpq/URI к пустой тестовой базе (нужен psql). Всё выполняется в "
        "одной транзакции и откатывается, тела PL/pgSQL проверяются (check_function_bodies = "
        "on). Код возврата 1, если что-то не загрузилось. Только --format terminal и json; "
        "--dialect выбирает детекторы и исправления для разбора ошибок.",
        "en": "Load ora2pg's generated PostgreSQL code into a real PostgreSQL and show which "
        "statements failed, which gap (GAP-NNN) each one is, which --fix repairs and which "
        "are only the echo of an earlier error. TARGET: docker - a throwaway postgres:16-alpine "
        "container (needs only docker), docker:IMAGE - an image of your own, or a libpq "
        "connection string/URI to an empty scratch database (needs psql). Everything runs in "
        "one transaction that is rolled back, and PL/pgSQL bodies are checked "
        "(check_function_bodies = on). Exit code 1 if anything failed to load. Only --format "
        "terminal and json; --dialect picks the detectors and fixes used to explain the errors.",
    },
    "help_prepare": {
        "ru": "Подготовить ИСХОДНЫЙ дамп к ora2pg: механически переписать то, на чём парсер "
        "ora2pg спотыкается, не меняя смысла. Для mysql - директивы DELIMITER (GAP-106/107), "
        "DEFINER (GAP-108), обёртки /*!50003 ... */ вокруг определений (GAP-109), CREATE TABLE "
        "IF NOT EXISTS (GAP-110); для oracle - строки q'[...]' (GAP-062) и IF NOT EXISTS "
        "(GAP-112); для mssql - имена в [скобках] (GAP-087). Как --fix: по умолчанию печатает "
        "diff, --write перезаписывает файлы (работайте с копией дампа).",
        "en": "Prepare the SOURCE dump for ora2pg: mechanically rewrite what ora2pg's parser "
        "trips over, without changing its meaning. For mysql, DELIMITER directives "
        "(GAP-106/107), DEFINER (GAP-108), /*!50003 ... */ wrappers around definitions "
        "(GAP-109), CREATE TABLE IF NOT EXISTS (GAP-110); for oracle, q'[...]' strings "
        "(GAP-062) and IF NOT EXISTS (GAP-112); for mssql, [bracketed] names (GAP-087). Like "
        "--fix: prints a diff by default, --write rewrites the files (work on a copy of the "
        "dump).",
    },
    "help_write": {
        "ru": "Вместе с --fix или --prepare: реально перезаписать файлы на диске вместо "
        "печати diff. Без них ни на что не влияет.",
        "en": "With --fix or --prepare: actually rewrite the files on disk instead of "
        "printing a diff. Has no effect without them.",
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
        "ru": "что сломается при переносе в PostgreSQL через ora2pg",
        "en": "what breaks when ora2pg moves a schema to PostgreSQL",
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
    # No "(requires ora2pg)" qualifier in the label: it duplicated what
    # connect_by_missing_ora2pg already says at the moment it matters
    # ("... contains CONNECT BY, but ora2pg was not found -- check
    # skipped"), and the two together did not fit the 80-column row --
    # the label was clipped mid-word on the right edge. The qualifier
    # survives where it is actionable: this message, and --help's own
    # text for --check-connect-by.
    "tui_connect_by_checkbox": {
        "ru": "Проверить CONNECT BY",
        "en": "Check CONNECT BY",
    },
    "tui_baseline_input_placeholder": {
        "ru": "Файл baseline (опционально — сравнить или сверить с ним)",
        "en": "Baseline file (optional -- compare or verify against it)",
    },
    # Shortened for the same reason -- the long form left the baseline
    # path input beside it 10 columns wide in Russian. "post-migration
    # output" is the part that disambiguates the mode; "scan as" was
    # doing no work the surrounding screen does not already do.
    "tui_verify_checkbox": {
        "ru": "Режим verify (вывод после миграции)",
        "en": "Verify mode (post-migration output)",
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
    # The key line at the bottom of each TUI screen: "key|what it does".
    "tui_hint_tab": {"ru": "tab|следующее поле", "en": "tab|next field"},
    "tui_hint_enter": {"ru": "enter|выбрать", "en": "enter|select"},
    "tui_hint_move": {"ru": "up/down|по находкам", "en": "up/down|move through findings"},
    "tui_hint_back": {"ru": "esc|назад", "en": "esc|back"},
    "tui_hint_quit": {"ru": "q|выход", "en": "q|quit"},
    "tui_elapsed": {"ru": "{s} с", "en": "{s}s"},
    "term_scanning": {"ru": "Сканирование {file} ({i} из {n})", "en": "Scanning {file} ({i} of {n})"},
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
    "tui_effort_caveat": {"ru": "(грубая эвристика, не измерение)", "en": "(a rough heuristic, not a measurement)"},
    "tui_scanned_path": {"ru": "Просканировано: {path}", "en": "Scanned: {path}"},
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




