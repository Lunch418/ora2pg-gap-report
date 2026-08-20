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

from ora2pg_gap_report.baseline import load_baseline, save_baseline
from ora2pg_gap_report.tui_app import (
    GapReportApp,
    ResultsScreen,
    ScanScreen,
    VerifyResultsScreen,
    scan_path,
    scan_paths,
)

SAMPLES = Path(__file__).resolve().parents[1] / "docs" / "research" / "samples"


async def _wait_until(pilot, condition, timeout: float = 5.0) -> None:
    async def _poll():
        while not condition():
            await pilot.pause()
            await asyncio.sleep(0.01)

    await asyncio.wait_for(_poll(), timeout=timeout)
    # The condition going true (a new Screen object showing up) doesn't
    # guarantee that screen has finished composing/laying out yet -- a
    # click issued right on its heels can resolve against a still-settling
    # DOM and land on the wrong widget entirely (confirmed: it lands on
    # the Footer's command-palette hint instead of the button underneath
    # it, opening the palette instead of clicking through). One more
    # pause() drains whatever layout work is still pending before this
    # returns control to the caller.
    await pilot.pause()


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


def test_scan_paths_combines_multiple_files():
    a = SAMPLES / "compound_trigger_apress.sql"
    b = SAMPLES / "logger.pkb"
    findings_a, objects_a, _ = scan_path(a)
    findings_b, objects_b, _ = scan_path(b)

    combined, objects_combined, warnings = scan_paths([a, b])
    assert warnings == []
    assert objects_combined == objects_a + objects_b
    assert len(combined) == len(findings_a) + len(findings_b)
    assert {f.source_file for f in combined} == {str(a), str(b)}


def test_scan_paths_dedupes_the_same_file_reached_twice():
    a = SAMPLES / "compound_trigger_apress.sql"
    findings_once, _, _ = scan_path(a)
    combined, _, warnings = scan_paths([a, a])
    assert warnings == []
    assert len(combined) == len(findings_once)


@pytest.mark.asyncio
async def test_add_to_selection_queues_multiple_paths_for_one_scan():
    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        assert isinstance(scan_screen, ScanScreen)

        scan_screen.selected_path = SAMPLES / "compound_trigger_apress.sql"
        await pilot.click("#add-path-btn")
        # Button.press() adds an "-active" CSS class for its 0.2s pressed
        # animation and ignores clicks while it's set (see Button._on_click)
        # -- clicking the *same* button again right away, as this test
        # does, gets silently swallowed unless we actually wait out that
        # window first. A plain pilot.pause() only drains the message
        # queue, it doesn't advance wall-clock time the timer is running
        # against.
        await pilot.pause(0.25)
        scan_screen.selected_path = SAMPLES / "logger.pkb"
        await pilot.click("#add-path-btn")
        await pilot.pause(0.25)
        assert scan_screen.selected_paths == [
            SAMPLES / "compound_trigger_apress.sql",
            SAMPLES / "logger.pkb",
        ]

        await pilot.click("#scan-btn")
        await _wait_until(pilot, lambda: isinstance(app.screen, ResultsScreen))

        results_screen = app.screen
        assert {Path(f.source_file) for f in results_screen.all_findings} == {
            SAMPLES / "compound_trigger_apress.sql",
            SAMPLES / "logger.pkb",
        }


@pytest.mark.asyncio
async def test_clear_selection_empties_the_queued_paths():
    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        scan_screen.selected_path = SAMPLES / "logger.pkb"
        await pilot.click("#add-path-btn")
        assert scan_screen.selected_paths
        await pilot.click("#clear-paths-btn")
        assert scan_screen.selected_paths == []


@pytest.mark.asyncio
async def test_add_to_selection_without_a_highlighted_path_shows_a_status_error():
    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        await pilot.click("#add-path-btn")
        assert scan_screen.selected_paths == []
        assert "first" in scan_screen.query_one("#status").content


@pytest.mark.asyncio
async def test_connect_by_checkbox_checks_or_warns_without_crashing():
    # Whether ora2pg happens to be installed in the environment running
    # this test or not, this should never blow up -- either a real
    # connect_by finding comes back, or a graceful "ora2pg not found"
    # warning does (same tolerance test_cli.py's own connect-by tests
    # apply by skipping the live-integration variant instead).
    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        scan_screen.selected_path = SAMPLES / "connect_by_hierarchy_pkg.sql"
        await pilot.click("#connect-by-checkbox")
        await pilot.click("#scan-btn")
        await _wait_until(pilot, lambda: isinstance(app.screen, ResultsScreen))

        results_screen = app.screen
        assert any(f.detector == "connect_by" for f in results_screen.all_findings) or any(
            "ora2pg" in w for w in results_screen.warnings
        )


@pytest.mark.asyncio
async def test_save_baseline_button_writes_a_loadable_baseline_file(tmp_path):
    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        scan_screen.selected_path = SAMPLES / "compound_trigger_apress.sql"
        await pilot.click("#scan-btn")
        await _wait_until(pilot, lambda: isinstance(app.screen, ResultsScreen))

        results_screen = app.screen
        out_path = tmp_path / "baseline.json"
        results_screen.query_one("#save-baseline-input").value = str(out_path)
        await pilot.click("#save-baseline-btn")
        await pilot.pause()

        assert out_path.exists()
        baseline = load_baseline(out_path)
        assert len(baseline) == len(results_screen.all_findings)
        assert "Saved" in results_screen.query_one("#save-status").content


@pytest.mark.asyncio
async def test_save_baseline_button_without_a_path_shows_an_error():
    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        scan_screen.selected_path = SAMPLES / "compound_trigger_apress.sql"
        await pilot.click("#scan-btn")
        await _wait_until(pilot, lambda: isinstance(app.screen, ResultsScreen))

        results_screen = app.screen
        await pilot.click("#save-baseline-btn")
        await pilot.pause()
        assert "Enter a path first" in results_screen.query_one("#save-status").content


@pytest.mark.asyncio
async def test_scanning_with_a_baseline_file_shows_new_and_resolved_counts(tmp_path):
    findings, _, _ = scan_path(SAMPLES / "compound_trigger_apress.sql")
    baseline_path = tmp_path / "before.json"
    save_baseline(findings, baseline_path)

    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        scan_screen.selected_path = SAMPLES / "compound_trigger_apress.sql"
        scan_screen.query_one("#baseline-input").value = str(baseline_path)
        await pilot.click("#scan-btn")
        await _wait_until(pilot, lambda: isinstance(app.screen, ResultsScreen))

        results_screen = app.screen
        assert results_screen.baseline_diff is not None
        # Scanned the exact same file again with nothing changed --
        # everything should land as unchanged, nothing new or resolved.
        assert results_screen.baseline_diff.new == []
        assert results_screen.baseline_diff.resolved == []
        assert results_screen.baseline_diff.unchanged_count == len(findings)
        assert "unchanged" in results_screen._summary_text()


@pytest.mark.asyncio
async def test_scanning_with_a_missing_baseline_file_shows_an_error_and_stays_on_scan_screen(tmp_path):
    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        scan_screen.selected_path = SAMPLES / "compound_trigger_apress.sql"
        scan_screen.query_one("#baseline-input").value = str(tmp_path / "does_not_exist.json")
        await pilot.click("#scan-btn")
        await _wait_until(
            pilot, lambda: "Couldn't load baseline" in scan_screen.query_one("#status").content
        )
        assert isinstance(app.screen, ScanScreen)


@pytest.mark.asyncio
async def test_verify_mode_compares_against_baseline_and_shows_verify_results(tmp_path):
    # bulk_collect (GAP-003) is VERBATIM per verification.py -- ora2pg
    # copies the syntax unchanged, so re-scanning the exact same source as
    # "generated output" should come back STILL_PRESENT with an unchanged
    # count.
    findings, _, _ = scan_path(SAMPLES / "logger.pkb")
    baseline_path = tmp_path / "before.json"
    save_baseline(findings, baseline_path)

    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        scan_screen.selected_path = SAMPLES / "logger.pkb"
        scan_screen.query_one("#baseline-input").value = str(baseline_path)
        await pilot.click("#verify-checkbox")
        await pilot.click("#scan-btn")
        await _wait_until(pilot, lambda: isinstance(app.screen, VerifyResultsScreen))

        verify_screen = app.screen
        assert verify_screen.results
        bulk_collect = next(r for r in verify_screen.results if r.detector == "bulk_collect")
        assert bulk_collect.status == "still_present"
        assert bulk_collect.post_migration_count == bulk_collect.baseline_count


@pytest.mark.asyncio
async def test_verify_checkbox_without_a_baseline_shows_a_status_error():
    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        scan_screen.selected_path = SAMPLES / "logger.pkb"
        await pilot.click("#verify-checkbox")
        await pilot.click("#scan-btn")
        await pilot.pause()
        assert isinstance(app.screen, ScanScreen)
        assert "requires a baseline" in scan_screen.query_one("#status").content


@pytest.mark.asyncio
async def test_verify_mode_conflicts_with_connect_by_checkbox(tmp_path):
    baseline_path = tmp_path / "before.json"
    save_baseline([], baseline_path)

    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        scan_screen.selected_path = SAMPLES / "logger.pkb"
        scan_screen.query_one("#baseline-input").value = str(baseline_path)
        await pilot.click("#verify-checkbox")
        await pilot.click("#connect-by-checkbox")
        await pilot.click("#scan-btn")
        await pilot.pause()
        assert isinstance(app.screen, ScanScreen)
        assert "can't be combined" in scan_screen.query_one("#status").content


@pytest.mark.asyncio
async def test_verify_back_button_returns_to_scan_screen(tmp_path):
    baseline_path = tmp_path / "before.json"
    save_baseline([], baseline_path)

    app = GapReportApp(start_path=SAMPLES)
    async with app.run_test() as pilot:
        await pilot.pause()
        scan_screen = app.screen
        scan_screen.selected_path = SAMPLES / "logger.pkb"
        scan_screen.query_one("#baseline-input").value = str(baseline_path)
        await pilot.click("#verify-checkbox")
        await pilot.click("#scan-btn")
        await _wait_until(pilot, lambda: isinstance(app.screen, VerifyResultsScreen))

        await pilot.click("#verify-back-btn")
        await pilot.pause()
        assert isinstance(app.screen, ScanScreen)
