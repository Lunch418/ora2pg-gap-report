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
