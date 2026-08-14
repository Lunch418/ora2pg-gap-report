from rich.console import Console

from ora2pg_gap_report.models import Finding
from ora2pg_gap_report.terminal_report import render


def _finding(**kwargs):
    defaults = dict(
        detector="x",
        severity="high",
        object_name="PKG.FOO",
        line=10,
        snippet="pragma autonomous_transaction;",
        message="explanation text",
        source_file="foo.pkb",
    )
    defaults.update(kwargs)
    return Finding(**defaults)


def test_render_empty_findings_shows_a_positive_panel():
    console = Console(record=True, width=100)
    render([], console=console)
    text = console.export_text()
    assert "не найдено" in text


def test_render_shows_summary_counts_and_every_finding():
    findings = [
        _finding(severity="high", object_name="PKG.A"),
        _finding(severity="medium", object_name="PKG.B", snippet="s2", message="m2"),
    ]
    console = Console(record=True, width=200)
    render(findings, console=console)
    text = console.export_text()

    assert "Найдено проблемных объектов: 2" in text
    assert "high: 1" in text
    assert "medium: 1" in text
    assert "PKG.A" in text
    assert "PKG.B" in text
    assert "Грубая оценка ручной доработки" in text


def test_render_handles_a_severity_outside_high_medium_low_without_crashing():
    findings = [_finding(severity="critical")]
    console = Console(record=True, width=200)
    render(findings, console=console)  # must not raise
    text = console.export_text()

    assert "other: 1" in text  # effort_estimator's catch-all bucket
    assert "critical" in text  # still shown verbatim in the per-row column


def test_render_shows_source_file_column():
    findings = [_finding(source_file="docs/samples/logger.pkb")]
    console = Console(record=True, width=200)
    render(findings, console=console)
    assert "logger.pkb" in console.export_text()


def test_render_does_not_crash_on_bracket_content_in_finding_fields():
    # Finding content comes straight from the Oracle files being scanned —
    # arbitrary text, not our own trusted markup. A file path/snippet
    # containing brackets used to raise rich.errors.MarkupError (mismatched
    # closing tag) because add_row() received plain strings, which Rich
    # parses as its own markup language by default.
    findings = [
        _finding(
            source_file="notes[/archive].sql",
            object_name="PKG.ARR[I][J]",
            snippet="arr[i][j] := 1;",
            message="see arr[i] for details",
        )
    ]
    console = Console(record=True, width=200)
    render(findings, console=console)  # must not raise MarkupError
    text = console.export_text()

    # and the content must survive verbatim, not be silently swallowed as
    # if it were a (mismatched or valid-looking) style tag
    assert "notes[/archive].sql" in text
    assert "PKG.ARR[I][J]" in text
    assert "arr[i][j] := 1;" in text


def test_render_does_not_strip_content_that_looks_like_a_valid_style_tag():
    # A snippet containing something that happens to match a real Rich
    # style name (e.g. "[red]") must render literally, not be interpreted
    # and stripped as coloured markup.
    findings = [_finding(snippet="v_colors[red] := 1;")]
    console = Console(record=True, width=200)
    render(findings, console=console)
    assert "v_colors[red] := 1;" in console.export_text()


def test_render_shows_top_objects_tree_when_multiple_objects_present():
    findings = [
        _finding(object_name="PKG.A", severity="high"),
        _finding(object_name="PKG.A", severity="medium", snippet="s2"),
        _finding(object_name="PKG.B", severity="low", snippet="s3"),
    ]
    console = Console(record=True, width=200)
    render(findings, console=console)
    text = console.export_text()
    assert "Объекты с наибольшим числом находок" in text
    assert "PKG.A" in text
    assert "2 находок" in text


def test_render_skips_top_objects_tree_when_only_one_object():
    findings = [_finding(object_name="PKG.A"), _finding(object_name="PKG.A", snippet="s2")]
    console = Console(record=True, width=200)
    render(findings, console=console)
    assert "Объекты с наибольшим числом находок" not in console.export_text()


def test_render_shows_elapsed_time_and_objects_scanned_when_provided():
    findings = [_finding()]
    console = Console(record=True, width=200)
    render(findings, console=console, elapsed_seconds=1.23, objects_scanned=7)
    text = console.export_text()
    assert "Время анализа: 1.2 с" in text
    assert "Объектов просканировано: 7" in text


def test_render_omits_elapsed_time_and_objects_scanned_when_not_provided():
    findings = [_finding()]
    console = Console(record=True, width=200)
    render(findings, console=console)
    text = console.export_text()
    assert "Время анализа" not in text
    assert "Объектов просканировано" not in text


def test_render_shows_best_expected_worst_case_effort():
    findings = [_finding(severity="high")]
    console = Console(record=True, width=200)
    render(findings, console=console)
    text = console.export_text()
    assert "лучший случай" in text
    assert "среднее" in text
    assert "худший случай" in text


def test_top_objects_tree_truncates_beyond_the_limit_and_notes_the_remainder():
    findings = [_finding(object_name=f"PKG.OBJ{i}", snippet=f"s{i}") for i in range(15)]
    console = Console(record=True, width=200)
    render(findings, console=console)
    text = console.export_text()
    assert "и ещё 5 объект(ов)" in text


def test_render_shows_stats_even_when_filters_leave_no_findings():
    # objects_scanned/elapsed_seconds are computed before any --severity/
    # --object filtering happens in cli.py -- if the filters legitimately
    # exclude every finding, render() used to hit the empty-findings early
    # return before ever looking at those parameters, silently dropping
    # them from the output.
    console = Console(record=True, width=200)
    render([], console=console, elapsed_seconds=2.5, objects_scanned=3)
    text = console.export_text()
    assert "Объектов просканировано: 3" in text
    assert "Время анализа: 2.5 с" in text
