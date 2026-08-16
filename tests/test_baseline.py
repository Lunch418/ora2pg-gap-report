import json

import pytest

from ora2pg_gap_report.baseline import (
    BaselineLoadError,
    compute_fingerprints,
    diff_against_baseline,
    load_baseline,
    save_baseline,
)
from ora2pg_gap_report.models import Finding


def _finding(**overrides) -> Finding:
    base = dict(
        detector="read_only_table",
        severity="high",
        object_name="AUDIT_LOG",
        line=4,
        snippet="READ ONLY",
        message="msg",
        source_file="schema/audit.sql",
    )
    base.update(overrides)
    return Finding(**base)


def test_fingerprint_is_stable_across_different_line_numbers():
    f1 = _finding(line=4)
    f2 = _finding(line=99)
    assert compute_fingerprints([f1]) == compute_fingerprints([f2])


def test_fingerprint_differs_for_different_objects():
    f1 = _finding(object_name="AUDIT_LOG")
    f2 = _finding(object_name="OTHER_TABLE")
    assert compute_fingerprints([f1]) != compute_fingerprints([f2])


def test_fingerprint_disambiguates_repeated_identical_findings_by_occurrence():
    # Same detector/file/object/snippet twice in one scan (e.g. the same
    # DBMS_LOB call appearing on two different lines of the same package)
    # must not collapse into a single fingerprint.
    f1 = _finding(line=10)
    f2 = _finding(line=20)
    fps = compute_fingerprints([f1, f2])
    assert fps[0] != fps[1]
    assert len(set(fps)) == 2


def test_save_and_load_round_trip(tmp_path):
    findings = [_finding(object_name="AUDIT_LOG"), _finding(object_name="CUSTOMERS", line=7)]
    path = tmp_path / "baseline.json"
    save_baseline(findings, path)

    baseline = load_baseline(path)
    assert len(baseline) == 2
    fps = compute_fingerprints(findings)
    assert set(baseline.keys()) == set(fps)


def test_save_baseline_is_valid_json_with_schema_version(tmp_path):
    path = tmp_path / "baseline.json"
    save_baseline([_finding()], path)
    raw = json.loads(path.read_text())
    assert raw["schema_version"] == 1
    assert len(raw["findings"]) == 1
    assert raw["findings"][0]["fingerprint"]
    assert raw["findings"][0]["object_name"] == "AUDIT_LOG"


def test_load_baseline_missing_file_raises_baseline_load_error(tmp_path):
    with pytest.raises(BaselineLoadError):
        load_baseline(tmp_path / "does_not_exist.json")


def test_load_baseline_invalid_json_raises_baseline_load_error(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not valid json")
    with pytest.raises(BaselineLoadError):
        load_baseline(path)


def test_load_baseline_wrong_shape_raises_baseline_load_error(tmp_path):
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps({"hello": "world"}))
    with pytest.raises(BaselineLoadError):
        load_baseline(path)


def test_diff_identical_scan_is_all_unchanged(tmp_path):
    findings = [_finding(object_name="AUDIT_LOG"), _finding(object_name="CUSTOMERS", line=7)]
    path = tmp_path / "baseline.json"
    save_baseline(findings, path)
    baseline = load_baseline(path)

    diff = diff_against_baseline(findings, baseline)
    assert diff.new == []
    assert diff.resolved == []
    assert diff.unchanged_count == 2


def test_diff_detects_new_and_resolved(tmp_path):
    old_findings = [_finding(object_name="AUDIT_LOG"), _finding(object_name="CUSTOMERS", line=7)]
    path = tmp_path / "baseline.json"
    save_baseline(old_findings, path)
    baseline = load_baseline(path)

    new_findings = [_finding(object_name="AUDIT_LOG"), _finding(object_name="ORDERS", line=3)]
    diff = diff_against_baseline(new_findings, baseline)

    assert len(diff.new) == 1
    assert diff.new[0].object_name == "ORDERS"
    assert len(diff.resolved) == 1
    assert diff.resolved[0]["object_name"] == "CUSTOMERS"
    assert diff.unchanged_count == 1
