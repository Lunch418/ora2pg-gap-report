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


def test_main_reports_unreadable_file_as_error_not_traceback(tmp_path, capsys, monkeypatch):
    # Simulate a read failure (e.g. permission denied) via monkeypatch
    # rather than chmod(0o000): chmod is a no-op against a root process
    # (as this sandbox runs), so it wouldn't actually reproduce the failure.
    unreadable = tmp_path / "secret.pkb"
    unreadable.write_text("create or replace package body x as end x; /")
    original_read_text = Path.read_text

    def boom(self, *args, **kwargs):
        if self == unreadable:
            raise PermissionError("Permission denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", boom)

    exit_code = main([str(unreadable)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert str(unreadable) in captured.err


def test_main_stamps_source_file_on_every_finding(tmp_path):
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
    by_object = {item["object_name"]: item["source_file"] for item in data}
    assert by_object["LOGGER.PURGE_ALL"].endswith("logger.pkb")
    assert by_object["TR_CONSTRUCTORS_CTI"].endswith("compound_trigger_apress.sql")


def test_main_merges_and_resorts_findings_across_multiple_files(tmp_path):
    # file A: only a medium-severity dbms_utl_calls finding.
    # file B: a high-severity autonomous_tx finding.
    # Passed in an order where A's medium would print before B's high if
    # the per-file results were merely concatenated without re-sorting.
    file_a = tmp_path / "a_medium.pkb"
    file_a.write_text(
        """
        create or replace package body aaa_pkg as
          procedure foo is
          begin
            utl_file.fopen('DIR', 'f', 'r');
          end foo;
        end aaa_pkg;
        /
        """
    )
    file_b = tmp_path / "b_high.pkb"
    file_b.write_text(
        """
        create or replace package body bbb_pkg as
          procedure bar is
            pragma autonomous_transaction;
          begin
            commit;
          end bar;
        end bbb_pkg;
        /
        """
    )

    output_path = tmp_path / "report.json"
    exit_code = main(
        [str(file_a), str(file_b), "--format", "json", "--output", str(output_path)]
    )
    assert exit_code == 0
    data = json.loads(output_path.read_text())
    assert data[0]["severity"] == "high"
    assert data[0]["object_name"] == "BBB_PKG.BAR"
    assert data[-1]["severity"] == "medium"
