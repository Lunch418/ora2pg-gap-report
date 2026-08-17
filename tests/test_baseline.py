import json

import pytest

from ora2pg_gap_report.baseline import (
    BaselineLoadError,
    diff_against_baseline,
    group_key,
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


def test_group_key_is_stable_across_different_line_numbers():
    f1 = _finding(line=4)
    f2 = _finding(line=99)
    assert group_key(f1) == group_key(f2)


def test_group_key_differs_for_different_objects():
    f1 = _finding(object_name="AUDIT_LOG")
    f2 = _finding(object_name="OTHER_TABLE")
    assert group_key(f1) != group_key(f2)


def test_save_and_load_round_trip(tmp_path):
    findings = [_finding(object_name="AUDIT_LOG"), _finding(object_name="CUSTOMERS", line=7)]
    path = tmp_path / "baseline.json"
    save_baseline(findings, path)

    records = load_baseline(path)
    assert len(records) == 2
    assert {rec["object_name"] for rec in records} == {"AUDIT_LOG", "CUSTOMERS"}
    assert all(rec["group_key"] for rec in records)


def test_save_baseline_is_valid_json_with_schema_version(tmp_path):
    path = tmp_path / "baseline.json"
    save_baseline([_finding()], path)
    raw = json.loads(path.read_text())
    assert raw["schema_version"] == 1
    assert len(raw["findings"]) == 1
    assert raw["findings"][0]["group_key"]
    assert raw["findings"][0]["object_name"] == "AUDIT_LOG"


def test_load_baseline_missing_file_raises_baseline_load_error(tmp_path):
    with pytest.raises(BaselineLoadError):
        load_baseline(tmp_path / "does_not_exist.json")


def test_load_baseline_invalid_json_raises_baseline_load_error(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not valid json")
    with pytest.raises(BaselineLoadError):
        load_baseline(path)


def test_load_baseline_non_utf8_raises_baseline_load_error(tmp_path):
    path = tmp_path / "binary.json"
    path.write_bytes(b"\xff\xfe\x00\x01garbage")
    with pytest.raises(BaselineLoadError):
        load_baseline(path)


def test_load_baseline_wrong_shape_raises_baseline_load_error(tmp_path):
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps({"hello": "world"}))
    with pytest.raises(BaselineLoadError):
        load_baseline(path)


def test_load_baseline_missing_group_key_raises_baseline_load_error(tmp_path):
    path = tmp_path / "no_group_key.json"
    path.write_text(json.dumps({"schema_version": 1, "findings": [{"object_name": "X"}]}))
    with pytest.raises(BaselineLoadError):
        load_baseline(path)


def test_load_baseline_rejects_a_mismatched_schema_version(tmp_path):
    path = tmp_path / "future.json"
    path.write_text(json.dumps({"schema_version": 999, "findings": []}))
    with pytest.raises(BaselineLoadError):
        load_baseline(path)


def test_load_baseline_error_messages_are_english_when_lang_is_en(tmp_path):
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps({"hello": "world"}))
    with pytest.raises(BaselineLoadError, match="doesn't look like an ora2pg-gap-report baseline"):
        load_baseline(path, lang="en")


def test_load_baseline_schema_mismatch_message_is_english_when_lang_is_en(tmp_path):
    path = tmp_path / "future.json"
    path.write_text(json.dumps({"schema_version": 999, "findings": []}))
    with pytest.raises(BaselineLoadError, match="this version of the tool expects"):
        load_baseline(path, lang="en")


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


def test_diff_partial_fix_of_duplicate_findings_reports_correct_counts(tmp_path):
    # Two indistinguishable findings (same detector/file/object/snippet)
    # in the baseline, only one of them still present now. This must
    # report exactly 1 resolved / 0 new / 1 unchanged -- not misattribute
    # the surviving one as a new+resolved pair, which an earlier,
    # positional-index-based version of this module got backwards.
    old_findings = [_finding(line=10), _finding(line=20)]
    path = tmp_path / "baseline.json"
    save_baseline(old_findings, path)
    baseline = load_baseline(path)

    new_findings = [_finding(line=20)]  # only one of the two survives
    diff = diff_against_baseline(new_findings, baseline)

    assert len(diff.new) == 0
    assert len(diff.resolved) == 1
    assert diff.unchanged_count == 1


def test_diff_new_duplicate_finding_is_reported_as_new(tmp_path):
    old_findings = [_finding(line=10)]
    path = tmp_path / "baseline.json"
    save_baseline(old_findings, path)
    baseline = load_baseline(path)

    new_findings = [_finding(line=10), _finding(line=30)]
    diff = diff_against_baseline(new_findings, baseline)

    assert len(diff.new) == 1
    assert diff.resolved == []
    assert diff.unchanged_count == 1
