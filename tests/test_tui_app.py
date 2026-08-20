"""Tests for the --tui interactive mode. Driven through Textual's own Pilot
test harness (App.run_test()) -- clicks/keypresses are simulated, not typed
into a real terminal, which is what makes this reliably testable in CI at
all.

One thing this harness genuinely needs, that a synchronous test doesn't:
_run_scan() is a @work(thread=True) worker, so a click that triggers it
returns before the scan (running on a real OS thread) has necessarily
finished. Waiting on ALL of app.workers (the obvious-looking fix) is wrong
-- it also waits on Textual's own internal framework workers (e.g. a CSS
"_loader" worker), which can be in a CANCELLED state that makes the wait
raise WorkerCancelled for a worker this test never started and doesn't
care about. _wait_until() below just polls the actual condition instead."""

import asyncio
from pathlib import Path

import pytest

from ora2pg_gap_report.tui_app import GapReportApp, ResultsScreen, ScanScreen, scan_path

SAMPLES = Path(__file__).resolve().parents[1] / "docs" / "research" / "samples"


async def _wait_until(pilot, condition, timeout: float = 5.0) -> None:
    async def _poll():
        while not condition():
            await pilot.pause()
            await asyncio.sleep(0.01)

    await asyncio.wait_for(_poll(), timeout=timeout)


def test_scan_path_on_a_single_file_matches_scan_source():
    findings, objects_scanned, warnings = scan_path(SAMPLES / "compound_trigger_apress.sql")
    assert warnings == []
    assert objects_scanned >= 1
    assert findings
    assert all(f.source_file == str(SAMPLES / "compound_trigger_apress.sql") for f in findings)


def test_scan_path_on_a_directory_recurses():
    findings, objects_scanned, warnings = scan_path(SAMPLES)
    assert warnings == []
    assert objects_scanned > 1
    assert len({f.source_file for f in findings}) > 1


def test_scan_path_on_a_directory_with_no_matching_files_warns(tmp_path):
    (tmp_path / "readme.txt").write_text("not DDL")
    findings, objects_scanned, warnings = scan_path(tmp_path)
    assert findings == []
    assert objects_scanned == 0
    assert len(warnings) == 1
    assert str(tmp_path) in warnings[0]


def test_scan_path_on_a_missing_file_warns(tmp_path):
    findings, objects_scanned, warnings = scan_path(tmp_path / "does_not_exist.pkb")
    assert findings == []
    assert len(warnings) == 1
    assert "Not found" in warnings[0]


@pytest.mark.asyncio
async def test_app_starts_on_the_scan_screen():
    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ScanScreen)


@pytest.mark.asyncio
async def test_scan_button_without_a_selected_path_shows_a_status_error():
    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#scan-btn")
        await pilot.pause()
        # Still on ScanScreen -- nothing was selected, so nothing to scan.
        assert isinstance(app.screen, ScanScreen)
        status = app.screen.query_one("#status")
        assert "Pick a file or directory" in status.content


@pytest.mark.asyncio
async def test_scanning_a_file_pushes_results_screen_with_its_findings():
    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        assert isinstance(scan_screen, ScanScreen)
        scan_screen.selected_path = SAMPLES / "compound_trigger_apress.sql"
        await pilot.click("#scan-btn")
        await _wait_until(pilot, lambda: isinstance(app.screen, ResultsScreen))

        results_screen = app.screen
        assert isinstance(results_screen, ResultsScreen)
        assert results_screen.findings
        assert results_screen.scanned_path == str(SAMPLES / "compound_trigger_apress.sql")


@pytest.mark.asyncio
async def test_severity_filter_is_applied_before_showing_results():
    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        scan_screen.selected_path = SAMPLES  # whole directory -- mixed severities
        scan_screen.query_one("#severity-select").value = "high"
        await pilot.click("#scan-btn")
        await _wait_until(pilot, lambda: isinstance(app.screen, ResultsScreen))

        results_screen = app.screen
        assert results_screen.findings
        assert all(f.severity == "high" for f in results_screen.findings)


@pytest.mark.asyncio
async def test_english_language_translates_finding_messages():
    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        scan_screen.selected_path = SAMPLES / "compound_trigger_apress.sql"
        scan_screen.query_one("#lang-select").value = "en"
        await pilot.click("#scan-btn")
        await _wait_until(pilot, lambda: isinstance(app.screen, ResultsScreen))

        results_screen = app.screen
        assert results_screen.findings
        # Russian message text shouldn't have survived translation.
        assert not any(any("а" <= ch <= "я" or ch == "ё" for ch in f.message.lower()) for f in results_screen.findings)
        assert results_screen.lang == "en"


@pytest.mark.asyncio
async def test_selecting_a_row_shows_gap_and_failure_stage_in_the_detail_panel():
    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        scan_screen.selected_path = SAMPLES / "compound_trigger_apress.sql"  # GAP-004, semantic
        await pilot.click("#scan-btn")
        await _wait_until(pilot, lambda: isinstance(app.screen, ResultsScreen))

        table = app.screen.query_one("#findings-table")
        table.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        detail = app.screen.query_one("#detail")
        assert "GAP-004" in detail.content
        # Default lang is "ru" -- the short stage label is translated,
        # same as terminal_report.py's own explanation panel, not the raw
        # "semantic" constant.
        assert "тихая потеря поведения" in detail.content


@pytest.mark.asyncio
async def test_detail_panel_stage_label_respects_english_language():
    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        scan_screen.selected_path = SAMPLES / "compound_trigger_apress.sql"  # GAP-004, semantic
        scan_screen.query_one("#lang-select").value = "en"
        await pilot.click("#scan-btn")
        await _wait_until(pilot, lambda: isinstance(app.screen, ResultsScreen))

        table = app.screen.query_one("#findings-table")
        table.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        detail = app.screen.query_one("#detail")
        assert "GAP-004" in detail.content
        assert "silent behavior loss" in detail.content


@pytest.mark.asyncio
async def test_back_button_returns_to_scan_screen():
    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        scan_screen.selected_path = SAMPLES / "compound_trigger_apress.sql"
        await pilot.click("#scan-btn")
        await _wait_until(pilot, lambda: isinstance(app.screen, ResultsScreen))

        await pilot.click("#back-btn")
        await pilot.pause()
        assert isinstance(app.screen, ScanScreen)


@pytest.mark.asyncio
async def test_scanning_an_empty_result_set_shows_a_clean_summary():
    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        # file_util_pkg.pks has no findings of its own severity-filterable
        # kind guaranteed -- filter to a severity with zero matches instead,
        # to deterministically exercise the "no findings" summary text.
        scan_screen.selected_path = SAMPLES / "compound_trigger_apress.sql"
        scan_screen.query_one("#severity-select").value = "low"
        await pilot.click("#scan-btn")
        await _wait_until(pilot, lambda: isinstance(app.screen, ResultsScreen))

        results_screen = app.screen
        assert results_screen.findings == []
        summary = results_screen.query_one("#summary")
        assert "no problematic constructs found" in str(summary.content).lower()
