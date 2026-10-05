"""--format checklist: a Markdown task list of the migration's work, one
box per object and gap, that remembers its own progress.

A report says what is wrong today. A checklist is what a team works
through for weeks: it goes into the repository or an issue, people tick
boxes as they fix things, and it is regenerated as the code changes. So
regenerating must not throw the ticks away. When `--output` names a
checklist this tool wrote before, it is read first:

- a box someone ticked stays ticked;
- an item that is no longer found, in a file this run scanned again, is
  ticked automatically ("no longer found") -- the construct is gone;
- an item whose file this run did not scan keeps whatever state it had,
  so scanning a subset never marks the rest done.

Each item carries its identity in an HTML comment at the end of the line,
which GitHub and GitLab do not render: detector, object and file. A file
that exists but was not written by this tool is never overwritten
(ChecklistError), since `-o NOTES.md` by mistake must not eat someone's
notes.
"""

from __future__ import annotations

import dataclasses
import datetime
import re
from collections.abc import Iterable
from pathlib import Path
from typing import IO

from . import i18n, messages
from .baseline import _normalized_source_file
from .gap_registry import gap_by_detector
from .html_report import STAGES, group_by_gap, severity_rank, source_name, stage_key, stage_of
from .models import Finding
from .prepare import prepare_command
from .recipes import recipe_for, recipe_url

MARKER = "<!-- ora2pg-gap-report checklist v1 -->"
_ITEM_RE = re.compile(r"^- \[(?P<mark>[ xX])\] .*<!-- item: (?P<key>[^>]*?) -->\s*$")
_FIELD_SEP = " | "


class ChecklistError(Exception):
    """The --output file exists and is not a checklist this tool wrote."""


@dataclasses.dataclass(frozen=True)
class ItemKey:
    detector: str
    object_name: str
    source_file: str  # normalized, see baseline._normalized_source_file

    def encode(self) -> str:
        # The separator cannot appear in a detector name; in the other two
        # it is escaped, and so is the comment terminator.
        parts = (self.detector, self.object_name, self.source_file)
        return _FIELD_SEP.join(p.replace("|", "%7C").replace("-->", "--%3E") for p in parts)

    @classmethod
    def decode(cls, text: str) -> ItemKey | None:
        parts = text.split(_FIELD_SEP)
        if len(parts) != 3:
            return None
        detector, object_name, source_file = (p.replace("--%3E", "-->").replace("%7C", "|") for p in parts)
        return cls(detector, object_name, source_file)


@dataclasses.dataclass(frozen=True)
class Item:
    key: ItemKey
    lines: tuple[int, ...]  # where it is now; empty when no longer found
    state: str  # "open" | "ticked" | "gone" | "kept"
    # "kept": not scanned this time; `checked` says what it was before
    checked: bool


def read_previous(path: Path) -> dict[ItemKey, bool] | None:
    """The items of the checklist at `path` and whether each was ticked,
    or None if there is no file. Raises ChecklistError when the file is
    not one of ours."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except UnicodeDecodeError as exc:
        raise ChecklistError(str(path)) from exc
    if MARKER not in text:
        raise ChecklistError(str(path))
    items: dict[ItemKey, bool] = {}
    for line in text.splitlines():
        m = _ITEM_RE.match(line)
        if m is None:
            continue
        key = ItemKey.decode(m.group("key"))
        if key is not None:
            items[key] = m.group("mark") != " "
    return items


def build_items(
    findings: Iterable[Finding],
    previous: dict[ItemKey, bool] | None,
    scanned_files: Iterable[str],
) -> dict[str, list[Item]]:
    """Every item, current or remembered, grouped by detector."""
    now: dict[ItemKey, list[int]] = {}
    for f in findings:
        key = ItemKey(f.detector, f.object_name, _normalized_source_file(f.source_file) if f.source_file else "")
        now.setdefault(key, []).append(f.line)
    previous = previous or {}
    scanned = {_normalized_source_file(s) for s in scanned_files}

    by_detector: dict[str, list[Item]] = {}
    for key in now.keys() | previous.keys():
        if key in now:
            ticked = previous.get(key, False)
            state = "ticked" if ticked else "open"
            item = Item(key, tuple(sorted(set(now[key]))), state, ticked)
        elif key.source_file in scanned:
            item = Item(key, (), "gone", True)
        else:
            item = Item(key, (), "kept", previous[key])
        by_detector.setdefault(key.detector, []).append(item)
    for items in by_detector.values():
        items.sort(key=lambda i: (i.checked, i.key.source_file, i.key.object_name))
    return by_detector


def _detector_order(findings: list[Finding], detectors: Iterable[str]) -> list[str]:
    """The reports' gap order for what was found now; gaps known only from
    the previous checklist follow, by stage."""
    ordered = [g.detector for g in group_by_gap(findings)]
    rest = sorted(
        (d for d in detectors if d not in ordered),
        key=lambda d: (STAGES.index(stage_of(d)) if stage_of(d) in STAGES else len(STAGES), d),
    )
    return ordered + rest


def _code(text: str) -> str:
    """Inline code that cannot be broken by a backtick in the text."""
    return "`" + text.replace("`", "'") + "`"


def _lines_text(lines: tuple[int, ...], lang: str) -> str:
    shown = ", ".join(str(n) for n in lines[:8])
    if len(lines) > 8:
        shown += ", ..."
    return i18n.t(lang, "checklist_line" if len(lines) == 1 else "checklist_lines", lines=shown)


def write_checklist(
    findings: list[Finding],
    stream: IO[str],
    *,
    lang: str = "ru",
    previous: dict[ItemKey, bool] | None = None,
    scanned_files: Iterable[str] = (),
    version: str = "",
    today: datetime.date | None = None,
) -> None:
    items = build_items(findings, previous, scanned_files)
    all_items = [i for group in items.values() for i in group]
    done = sum(1 for i in all_items if i.checked)
    total = len(all_items)
    w = stream.write

    w(MARKER + "\n")
    w(f"# {i18n.t(lang, 'checklist_title', source=source_name(findings))}\n\n")
    date = (today or datetime.date.today()).isoformat()
    w(i18n.t(lang, "checklist_made", version=version, date=date) + "\n\n")
    if total:
        percent = round(100 * done / total)
        w(f"**{i18n.t(lang, 'checklist_progress', done=done, total=total, percent=percent)}**\n\n")
        w(i18n.t(lang, "checklist_how") + "\n\n")
    else:
        w(i18n.t(lang, "checklist_empty") + "\n")
        return

    for detector in _detector_order(findings, items):
        group = items[detector]
        gap = gap_by_detector(detector)
        number = f"GAP-{gap.number} " if gap is not None else ""
        title = messages.title(detector, lang)
        group_done = all(i.checked for i in group)
        heading = f"{number}{title}" + (f" - {i18n.t(lang, 'checklist_gap_done')}" if group_done else "")
        w(f"## {heading}\n\n")

        severities = sorted({f.severity for f in findings if f.detector == detector}, key=severity_rank)
        meta = []
        if severities:
            meta.append(severities[0])
        stage = stage_of(detector)
        if stage is not None:
            meta.append(i18n.t(lang, "checklist_breaks_at", stage=i18n.t(lang, f"stage_{stage_key(stage)}_name").lower()))
        open_count = sum(1 for i in group if not i.checked)
        meta.append(i18n.t(lang, "checklist_open_of", open=open_count, total=len(group)))
        w(" · ".join(meta) + "\n\n")

        if not group_done:
            hint = messages.remediation_hint(detector, lang)
            if hint:
                w(f"**{i18n.t(lang, 'report_gap_fix')}:** {hint}\n\n")
            command = prepare_command(detector)
            if command is not None:
                w(f"**{i18n.t(lang, 'report_gap_prepare')}:** `{command}`\n\n")
            recipe = recipe_for(detector)
            if recipe is not None:
                w(f"**{i18n.t(lang, 'report_gap_recipe')}:** [{recipe.title(lang)}]({recipe_url(recipe, lang)})\n\n")
            if gap is not None:
                w(f"**{i18n.t(lang, 'checklist_details')}:** `ora2pg-gap-report --explain GAP-{gap.number}`\n\n")

        for item in group:
            mark = "x" if item.checked else " "
            where = _code(item.key.source_file) if item.key.source_file else ""
            line = f"- [{mark}] {_code(item.key.object_name)}"
            if where:
                line += f" - {where}"
            if item.lines:
                line += f" {_lines_text(item.lines, lang)}"
            if item.state == "gone":
                line += f" - {i18n.t(lang, 'checklist_gone')}"
            elif item.state == "kept":
                line += f" - {i18n.t(lang, 'checklist_not_scanned')}"
            w(f"{line} <!-- item: {item.key.encode()} -->\n")
        w("\n")
