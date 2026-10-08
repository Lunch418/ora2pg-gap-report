"""Retake the README screenshots in docs/screenshots/.

    python scripts/screenshots.py

The terminal pictures are Rich's own recording of the real output, saved
as SVG and rendered by headless Chrome; the HTML report is rendered the
same way. The --migrate pictures come from a real run on the sample
packages: ora2pg from the docker image ora2pg:25.0 (or $ORA2PG_BIN) and
PostgreSQL 16 in docker. The TUI pictures are Textual's own screenshots of
the app driven by its test harness. Needs google-chrome, docker and the
[tui] extra.

When docker runs outside a sandbox that hides /tmp, nothing else is
needed; otherwise point TMPDIR at a directory docker can see.
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from ora2pg_gap_report import html_report
from ora2pg_gap_report.core import count_objects, expand_paths, scan_source
from ora2pg_gap_report.load_check import parse_target, run_load_check
from ora2pg_gap_report.migrate import run_migration
from ora2pg_gap_report.models import Finding
from ora2pg_gap_report.terminal_report import render, render_migration

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = Path("docs/research/samples")
CHROME = os.environ.get("CHROME", "google-chrome")
ORA2PG = os.environ.get("ORA2PG_BIN", "docker:ora2pg:25.0")
# Rich's SVG uses Fira Code, whose ligatures would draw -> as an arrow.
NO_LIGATURES = "<style>text, tspan { font-variant-ligatures: none; }</style>"


def _chrome(page: Path, png: Path, width: int, height: int) -> None:
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
         "--force-device-scale-factor=1", f"--window-size={width},{height}",
         f"--screenshot={png}", f"file://{page.resolve()}"],
        check=True, capture_output=True, timeout=120,
    )


def svg_to_png(svg: Path, png: Path, width: int, height: int | None) -> None:
    """The SVG at its natural proportions, `width` px wide, cut to `height`
    (or its own height): Chrome would otherwise shrink a long SVG to fit
    the window."""
    text = svg.read_text(encoding="utf-8").replace("<style>", NO_LIGATURES + "<style>", 1)
    svg.write_text(text, encoding="utf-8")
    vb = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', text)
    assert vb is not None
    natural = round(width * float(vb.group(2)) / float(vb.group(1)))
    page = svg.with_suffix(".page.html")
    page.write_text(
        '<!doctype html><html><body style="margin:0;background:#1e1e1e">'
        f'<img src="{svg.name}" style="display:block;width:{width}px"></body></html>',
        encoding="utf-8",
    )
    _chrome(page, png, width, min(height or natural, natural))


def record(work: Path, out: Path, title: str, draw: Callable[[Console], None], name: str, height: int | None) -> None:
    with open(os.devnull, "w", encoding="utf-8") as sink:
        console = Console(record=True, width=112, force_terminal=True, color_system="truecolor", file=sink)
        draw(console)
    svg = work / f"{name}.svg"
    console.save_svg(str(svg), title=title)
    svg_to_png(svg, out / f"{name}.png", 1400, height)


async def _tui_shots(work: Path, out: Path, lang: str, migrated: Path) -> None:
    """The results screen on the samples with one finding open, and the
    migrate screen after a run into `migrated`."""
    from ora2pg_gap_report.tui_app import GapReportApp, MigrateScreen, ResultsScreen

    app = GapReportApp(start_path=SAMPLES, lang=lang)
    async with app.run_test(size=(118, 40)) as pilot:
        await pilot.pause()
        app.screen.selected_path = SAMPLES  # type: ignore[attr-defined]
        await pilot.click("#scan-btn")
        while not isinstance(app.screen, ResultsScreen):
            await pilot.pause()
        table = app.screen.query_one("#findings-table")
        table.focus()
        for _ in range(3):
            await pilot.press("down")
        await pilot.pause()
        app.save_screenshot(str(work / f"tui.{lang}.svg"))

        await pilot.press("escape")
        await pilot.pause()
        await pilot.click("#migrate-btn")
        while not isinstance(app.screen, MigrateScreen):
            await pilot.pause()
        screen = app.screen
        screen.query_one("#migrate-out").value = str(migrated)  # type: ignore[attr-defined]
        screen.query_one("#migrate-ora2pg").value = ORA2PG  # type: ignore[attr-defined]
        screen.query_one("#migrate-load").value = True  # type: ignore[attr-defined]
        await pilot.click("#migrate-run-btn")
        while screen.result_text is None:
            await pilot.pause()
            await asyncio.sleep(0.2)
        await pilot.pause()
        app.save_screenshot(str(work / f"tui-migrate.{lang}.svg"))
    for name in (f"tui.{lang}", f"tui-migrate.{lang}"):
        svg_to_png(work / f"{name}.svg", out / f"{name}.png", 1400, None)


def main() -> int:
    os.chdir(ROOT)
    out = ROOT / "docs" / "screenshots"
    work = Path(tempfile.mkdtemp(prefix="screenshots-"))

    paths, _ = expand_paths([SAMPLES])
    findings: list[Finding] = []
    objects = 0
    start = time.perf_counter()
    for p in paths:
        text = p.read_text(encoding="utf-8", errors="replace")
        objects += count_objects(text)
        findings += [dataclasses.replace(f, source_file=str(p)) for f in scan_source(text)]
    elapsed = time.perf_counter() - start

    result = run_migration(paths, work / "out", ora2pg_bin=ORA2PG, lang="en")
    result.out_dir = Path("out")  # as the command line in the title names it
    load = run_load_check(result.converted, parse_target("docker"))

    for lang in ("en", "ru"):
        record(
            work, out, "ora2pg-gap-report docs/research/samples/",
            lambda c: render(findings, console=c, elapsed_seconds=elapsed, objects_scanned=objects, lang=lang),
            f"terminal.{lang}", 1460,
        )
        record(
            work, out, "ora2pg-gap-report --migrate out/ --load-check docker docs/research/samples/",
            lambda c: render_migration(result, load, console=c, lang=lang, load_check_asked=True),
            f"migrate.{lang}", None,
        )
        page = work / f"report.{lang}.html"
        with open(page, "w", encoding="utf-8") as report:
            html_report.write_html(findings, report, lang=lang, load=load)
        _chrome(page, out / f"html-report.{lang}.png", 1280, 1100)
        # From inside `work`, where docs/research/samples is a link to the
        # real one, so the screen shows the same short relative paths the
        # README's commands use, and out/ lands in the scratch directory.
        os.chdir(work)
        samples_link = work / SAMPLES
        if not samples_link.exists():
            samples_link.parent.mkdir(parents=True, exist_ok=True)
            samples_link.symlink_to(ROOT / SAMPLES)
        shutil.rmtree(work / "out", ignore_errors=True)
        asyncio.run(_tui_shots(work, out, lang, Path("out")))
        os.chdir(ROOT)
    print(f"written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
