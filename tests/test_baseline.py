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


# --- A-02 regression: group_key must not depend on how the path was spelled,
# only on which file it names, when both scans share a working directory
# (the --save/--baseline pair this exists for). ---


def test_group_key_is_stable_between_relative_and_absolute_spelling(tmp_path, monkeypatch):
    # The audit's own repro: `tool pkg.sql --save b.json` then
    # `tool "$PWD/pkg.sql" --baseline b.json` used to report the identical
    # finding as both NEW and RESOLVED instead of UNCHANGED.
    monkeypatch.chdir(tmp_path)
    relative = _finding(source_file="pkg.sql")
    absolute = _finding(source_file=str(tmp_path / "pkg.sql"))
    assert group_key(relative) == group_key(absolute)


def test_group_key_is_stable_across_redundant_path_segments(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    plain = _finding(source_file="schema/pkg.sql")
    noisy = _finding(source_file="./schema/../schema/pkg.sql")
    assert group_key(plain) == group_key(noisy)


def test_group_key_still_differs_for_genuinely_different_files(tmp_path, monkeypatch):
    # The normalization must not go so far it stops distinguishing files.
    monkeypatch.chdir(tmp_path)
    a = _finding(source_file="a.sql")
    b = _finding(source_file="b.sql")
    assert group_key(a) != group_key(b)


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
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["schema_version"] == 2
    assert len(raw["findings"]) == 1
    assert raw["findings"][0]["group_key"]
    assert raw["findings"][0]["object_name"] == "AUDIT_LOG"


def test_save_baseline_includes_gap_number_and_failure_stage(tmp_path):
    path = tmp_path / "baseline.json"
    save_baseline([_finding()], path)  # read_only_table -- GAP-026, failure_stage="semantic"
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["findings"][0]["gap_number"] == "026"
    assert raw["findings"][0]["failure_stage"] == "semantic"


def test_load_baseline_tolerates_a_snapshot_saved_before_gap_metadata_existed(tmp_path):
    # A --save file written by an older version of this tool has no
    # gap_number/failure_stage keys at all -- load_baseline() only ever
    # required group_key + schema_version (see its own body), so an old
    # snapshot must keep loading rather than suddenly erroring after an
    # upgrade.
    path = tmp_path / "old_baseline.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "findings": [
                    {
                        "group_key": "abc123",
                        "detector": "read_only_table",
                        "severity": "high",
                        "object_name": "AUDIT_LOG",
                        "line": 4,
                        "snippet": "READ ONLY",
                        "message": "msg",
                        "source_file": "schema/audit.sql",
                    }
                ],
            }
        )
    , encoding="utf-8")
    records = load_baseline(path)
    assert len(records) == 1
    assert records[0]["object_name"] == "AUDIT_LOG"
    assert "gap_number" not in records[0]


def test_load_baseline_missing_file_raises_baseline_load_error(tmp_path):
    with pytest.raises(BaselineLoadError):
        load_baseline(tmp_path / "does_not_exist.json")


def test_load_baseline_invalid_json_raises_baseline_load_error(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(BaselineLoadError):
        load_baseline(path)


def test_load_baseline_non_utf8_raises_baseline_load_error(tmp_path):
    path = tmp_path / "binary.json"
    path.write_bytes(b"\xff\xfe\x00\x01garbage")
    with pytest.raises(BaselineLoadError):
        load_baseline(path)


def test_load_baseline_wrong_shape_raises_baseline_load_error(tmp_path):
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps({"hello": "world"}), encoding="utf-8")
    with pytest.raises(BaselineLoadError):
        load_baseline(path)


def test_load_baseline_missing_group_key_raises_baseline_load_error(tmp_path):
    path = tmp_path / "no_group_key.json"
    path.write_text(json.dumps({"schema_version": 2, "findings": [{"object_name": "X"}]}), encoding="utf-8")
    with pytest.raises(BaselineLoadError):
        load_baseline(path)


def test_load_baseline_missing_detector_raises_baseline_load_error_not_keyerror(tmp_path):
    # verify_against_baseline() (verification.py) reads rec["detector"]
    # unconditionally -- a record with a group_key but no detector used to
    # sail through load_baseline()'s validation and blow up as a raw
    # KeyError from deep inside --verify instead of a clean, catchable
    # BaselineLoadError right here where the file is actually read.
    path = tmp_path / "no_detector.json"
    path.write_text(json.dumps({"schema_version": 2, "findings": [{"group_key": "abc123"}]}), encoding="utf-8")
    with pytest.raises(BaselineLoadError, match="detector"):
        load_baseline(path)


def test_load_baseline_rejects_a_mismatched_schema_version(tmp_path):
    path = tmp_path / "future.json"
    path.write_text(json.dumps({"schema_version": 999, "findings": []}), encoding="utf-8")
    with pytest.raises(BaselineLoadError):
        load_baseline(path)


def test_load_baseline_error_messages_are_english_when_lang_is_en(tmp_path):
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps({"hello": "world"}), encoding="utf-8")
    with pytest.raises(BaselineLoadError, match="doesn't look like an ora2pg-gap-report baseline"):
        load_baseline(path, lang="en")


def test_load_baseline_schema_mismatch_message_is_english_when_lang_is_en(tmp_path):
    path = tmp_path / "future.json"
    path.write_text(json.dumps({"schema_version": 999, "findings": []}), encoding="utf-8")
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
