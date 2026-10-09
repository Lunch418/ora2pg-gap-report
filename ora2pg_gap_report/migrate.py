"""--migrate OUT_DIR: the whole path from a source dump to PostgreSQL that
loads, in one run, using every other part of this tool.

1. scan      -- the findings for the source, as an HTML report and a
                checklist (both into OUT_DIR)
2. prepare   -- a copy of the source with --prepare's rewrites applied
3. convert   -- ora2pg, once per object type, on the prepared copy
4. fix       -- --fix's mechanical repairs on ora2pg's output
5. load      -- --load-check against a real PostgreSQL, when a target is
                given

Nothing here is new behaviour: each step is the mode of the same name,
run in the order a migration needs them, on files kept in one directory
so every stage can be looked at afterwards. The source files are never
touched -- the preparation works on copies.

OUT_DIR is ours: it gets a marker file, and a directory that exists
without one is refused, so pointing --migrate at the wrong place cannot
overwrite someone's files. Running again into the same OUT_DIR replaces
the generated files and keeps the checklist's ticks.
"""

from __future__ import annotations

import dataclasses
import io
import re
import shutil
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING
from pathlib import Path

from .autofix import FIXERS_BY_DIALECT
from . import source_fixes
from .checklist import ChecklistError, read_previous, write_checklist
from .core import scan_source
from .models import Finding
from .ora2pg_wrapper import CONVERT_TYPES, run_convert
from .prepare import PREPARERS_BY_DIALECT

if TYPE_CHECKING:
    from .load_check import LoadCheckResult

MARKER_NAME = ".ora2pg-gap-report-migrate"


class MigrateError(Exception):
    """The run cannot start (OUT_DIR is not ours) or ora2pg failed. Carries
    an i18n key and its arguments."""

    def __init__(self, key: str, **kwargs: object) -> None:
        super().__init__(key)
        self.key = key
        self.kwargs = kwargs


@dataclasses.dataclass
class MigrationResult:
    out_dir: Path
    sources: list[Path]
    findings: list[Finding]
    prepared_rewrites: int
    converted: list[Path]  # in load order
    fixes: int
    source_fixes: int = 0
    empty_types: list[str] = dataclasses.field(default_factory=list)


# Only a comment, a client setting or a psql command: what ora2pg writes for
# a type the input has nothing of.
_BOILERPLATE_RE = re.compile(r"^\s*(?:--.*|SET\s+\w+.*;|\\.*)?\s*$", re.IGNORECASE)


def _has_content(sql: str) -> bool:
    return any(not _BOILERPLATE_RE.match(line) for line in sql.splitlines())


def _content(sql: str) -> str:
    """`sql` without ora2pg's header and blank lines, for comparing two runs."""
    return "\n".join(line.rstrip() for line in sql.splitlines() if not _BOILERPLATE_RE.match(line))


def outside(sources: Sequence[Path], out_dir: Path) -> list[Path]:
    """`sources` without anything under `out_dir`. With OUT_DIR inside the
    directory being migrated, a rerun would otherwise read the last run's
    prepared/ and converted/ files as source -- and then clear them."""
    root = out_dir.resolve()
    return [p for p in sources if not p.resolve().is_relative_to(root)]


_PACKAGE_RE = re.compile(
    r"^[ \t]*CREATE\s+(?:OR\s+REPLACE\s+)?(?:(?:NON)?EDITIONABLE\s+)?PACKAGE\b",
    re.IGNORECASE | re.MULTILINE,
)
_SLASH_LINE_RE = re.compile(r"^[ \t]*/[ \t]*\r?$", re.MULTILINE)


def _package_spans(source: str) -> list[tuple[int, int]]:
    """Where each package spec and body is: from its CREATE up to the
    SQL*Plus `/` that ends it (or to the next package, or the end)."""
    from .plsql_lex import mask_strings_and_comments

    masked = mask_strings_and_comments(source)
    cuts: list[tuple[int, int]] = []
    for m in _PACKAGE_RE.finditer(masked):
        if cuts and m.start() < cuts[-1][1]:
            continue
        slash = _SLASH_LINE_RE.search(masked, m.end())
        nxt = _PACKAGE_RE.search(masked, m.end())
        end = min(x for x in (slash.end() if slash else len(source), nxt.start() if nxt else len(source)))
        cuts.append((m.start(), end))
    return cuts


def only_packages(source: str) -> str:
    """The package specs and bodies of `source`, nothing else.

    In file mode ora2pg's -t PACKAGE reads a package body up to the next
    package or the end of the file: an object after the last body -- a
    trigger, a procedure -- is glued into the last routine of it, which
    then fails to load. The PACKAGE run gets this text instead."""
    return "".join(source[start:end].rstrip("\n") + "\n" for start, end in _package_spans(source))


def without_packages(source: str) -> str:
    """`source` with every package spec and body cut out, each up to the
    SQL*Plus `/` that ends it (or to the next package, or the end).

    In file mode ora2pg's -t TYPE, FUNCTION and PROCEDURE do not stop at
    standalone objects: they also extract the types and routines declared
    inside packages, without the package's name. Run on the whole dump,
    every package member comes out twice -- once from -t PACKAGE, once
    unqualified -- and the copies fail to load against each other. Those
    runs get this text instead; -t PACKAGE gets only_packages()."""
    out: list[str] = []
    pos = 0
    for start, end in _package_spans(source):
        out.append(source[pos:start])
        pos = end
    out.append(source[pos:])
    return "".join(out)


def prepare_out_dir(out_dir: Path) -> None:
    """Make OUT_DIR ours, or refuse it. Empty or missing: created and
    marked. Marked: the generated parts are cleared for this run. Anything
    else: MigrateError, nothing touched."""
    marker = out_dir / MARKER_NAME
    if out_dir.exists() and any(out_dir.iterdir()) and not marker.exists():
        raise MigrateError("migrate_out_dir_not_ours", path=str(out_dir))
    out_dir.mkdir(parents=True, exist_ok=True)
    marker.write_text("Created by ora2pg-gap-report --migrate. Safe to delete with the directory.\n", encoding="utf-8")
    for generated in ("prepared", "converted"):
        shutil.rmtree(out_dir / generated, ignore_errors=True)


def run_migration(
    sources: Sequence[Path],
    out_dir: Path,
    *,
    dialect: str = "oracle",
    ora2pg_bin: str = "ora2pg",
    lang: str = "ru",
    version: str = "",
    progress: Callable[[str], None] | None = None,
) -> MigrationResult:
    """Steps 1-4 (load is the caller's, so it can reuse --load-check's own
    reporting). Raises MigrateError, or ora2pg_wrapper's errors."""
    say = progress or (lambda _key: None)
    sources = outside(sources, out_dir)
    prepare_out_dir(out_dir)

    # 1. scan
    say("migrate_step_scan")
    texts: dict[Path, str] = {}
    findings: list[Finding] = []
    for path in sources:
        text = path.read_bytes().decode("utf-8", errors="surrogateescape")
        texts[path] = text
        readable = text.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace")
        findings.extend(dataclasses.replace(f, source_file=str(path)) for f in scan_source(readable, dialect=dialect))

    from .html_report import write_html

    with open(out_dir / "report.html", "w", encoding="utf-8") as report:
        write_html(findings, report, lang=lang)
    checklist_path = out_dir / "MIGRATION.md"
    try:
        previous = read_previous(checklist_path)
    except ChecklistError:
        previous = None
    buffer = io.StringIO()
    write_checklist(
        findings, buffer, lang=lang, previous=previous, scanned_files=[str(p) for p in sources], version=version
    )
    checklist_path.write_text(buffer.getvalue(), encoding="utf-8")

    # 2. prepare -- one combined input, so ora2pg sees every package in the
    # same run and converts calls between them (see GAP-117).
    say("migrate_step_prepare")
    prepared_dir = out_dir / "prepared"
    prepared_dir.mkdir()
    rewrites = 0
    combined_parts: list[str] = []
    for path in sources:
        text = texts[path]
        for preparer in PREPARERS_BY_DIALECT[dialect]:
            text, applied = preparer(text)
            rewrites += applied
        (prepared_dir / path.name).write_bytes(text.encode("utf-8", errors="surrogateescape"))
        combined_parts.append(text if text.endswith("\n") else text + "\n")
    combined_text = "".join(combined_parts)
    combined = prepared_dir / "_all_sources.sql"
    combined.write_bytes(combined_text.encode("utf-8", errors="surrogateescape"))
    packages = prepared_dir / "_packages.sql"
    packages.write_bytes(only_packages(combined_text).encode("utf-8", errors="surrogateescape"))
    standalone = prepared_dir / "_standalone.sql"
    standalone.write_bytes(
        (without_packages(combined_text) if dialect == "oracle" else combined_text).encode(
            "utf-8", errors="surrogateescape"
        )
    )

    # 3. convert
    converted_dir = out_dir / "converted"
    converted_dir.mkdir()
    converted: list[Path] = []
    empty: list[str] = []
    # In file mode ora2pg's -t FUNCTION and -t PROCEDURE each extract
    # every standalone routine, functions and procedures alike, so the two
    # outputs are the same: loading both would create every routine twice
    # and report each of its errors twice. A type whose output repeats an
    # earlier one's is left out.
    seen: set[str] = set()
    for position, object_type in enumerate(CONVERT_TYPES[dialect], 1):
        say(f"migrate_step_convert:{object_type}")
        source_file = packages if object_type == "PACKAGE" else standalone
        sql = run_convert(source_file, object_type, dialect=dialect, ora2pg_bin=ora2pg_bin, lang=lang)
        if not _has_content(sql) or _content(sql) in seen:
            empty.append(object_type)
            continue
        seen.add(_content(sql))
        target = converted_dir / f"{position:02d}_{object_type}_output.sql"
        target.write_text(sql, encoding="utf-8")
        converted.append(target)

    # 4. fix -- --fix's repairs, then the ones that need the source
    # (source_fixes.py): which triggers were statement-level, what each
    # package constant's value is, which values an ENUM had.
    say("migrate_step_fix")
    fixes = 0
    source_repairs = 0
    readable = combined_text.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace")
    knowledge = source_fixes.learn(readable, dialect)
    for target in converted:
        text = target.read_text(encoding="utf-8")
        for fixer in FIXERS_BY_DIALECT[dialect]:
            text, applied = fixer(text)
            fixes += applied
        text, applied = source_fixes.apply(text, knowledge)
        source_repairs += applied
        target.write_text(text, encoding="utf-8")

    return MigrationResult(
        out_dir=out_dir,
        sources=list(sources),
        findings=findings,
        prepared_rewrites=rewrites,
        converted=converted,
        fixes=fixes,
        source_fixes=source_repairs,
        empty_types=empty,
    )


def load_and_record(result: MigrationResult, target: str, *, dialect: str = "oracle", lang: str = "ru") -> LoadCheckResult:
    """Step 5: load the converted files into `target` (as --load-check
    names it) and record the outcome in OUT_DIR -- the load card at the top
    of report.html, load-check.json for a pipeline, load-check.txt to read.
    The CLI and the TUI both run this, so both leave the same directory.
    Raises load_check.LoadCheckError."""
    from rich.console import Console

    from .atomic_write import open_text_atomic, write_text_atomic
    from .html_report import write_html
    from .load_check import parse_target, run_load_check
    from .report_generator import to_load_check_json
    from .terminal_report import render_load_check

    load = run_load_check(result.converted, parse_target(target), dialect=dialect)
    with open_text_atomic(result.out_dir / "report.html") as report_file:
        write_html(result.findings, report_file, lang=lang, load=load)
    write_text_atomic(result.out_dir / "load-check.json", to_load_check_json(load))
    buffer = io.StringIO()
    render_load_check(load, console=Console(file=buffer), lang=lang)
    write_text_atomic(result.out_dir / "load-check.txt", buffer.getvalue())
    return load

