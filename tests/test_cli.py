import json
from pathlib import Path

from src.cli import main, scan_source

SAMPLES = Path(__file__).resolve().parents[1] / "docs" / "research" / "samples"


def test_scan_source_runs_all_three_detectors_on_logger():
    source = (SAMPLES / "logger.pkb").read_text()
    findings = scan_source(source)
    detectors_seen = {f.detector for f in findings}
    assert detectors_seen == {"autonomous_tx", "dbms_utl_calls"}
    assert len(findings) == 8 + 17  # autonomous_tx + dbms_utl_calls, verified in their own tests


def test_scan_source_sorts_high_severity_first():
    source = (SAMPLES / "logger.pkb").read_text()
    findings = scan_source(source)
    severities = [f.severity for f in findings]
    assert severities == sorted(severities, key=lambda s: {"high": 0, "medium": 1, "low": 2}[s])


def test_main_end_to_end_markdown_to_stdout(capsys):
    exit_code = main([str(SAMPLES / "compound_trigger_apress.sql")])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "TR_CONSTRUCTORS_CTI" in captured.out
    assert "Грубая оценка" in captured.out


def test_main_end_to_end_json_to_file(tmp_path):
    output_path = tmp_path / "report.json"
    exit_code = main(
        [
            str(SAMPLES / "logger.pkb"),
            str(SAMPLES / "compound_trigger_apress.sql"),
            "--format",
            "json",
            "--output",
            str(output_path),
        ]
    )
    assert exit_code == 0
    data = json.loads(output_path.read_text())
    assert isinstance(data, list)
    object_names = {item["object_name"] for item in data}
    assert "TR_CONSTRUCTORS_CTI" in object_names
    assert "LOGGER.PURGE_ALL" in object_names


def test_main_reports_missing_file_as_error(capsys):
    exit_code = main([str(SAMPLES / "does_not_exist.sql")])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "does_not_exist.sql" in captured.err
