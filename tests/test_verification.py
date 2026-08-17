"""Tests for verification.py -- the detector-level (not finding-level)
post-migration status resolution. See its module docstring for why
matching is at detector granularity and why detectors split into
VERBATIM/NOT_VERIFIABLE."""

import glob
import os

from ora2pg_gap_report.models import Finding
from ora2pg_gap_report.verification import (
    VERIFICATION_MODE,
    DetectorVerification,
    verify_against_baseline,
)


def _baseline_record(detector: str, **overrides) -> dict:
    base = dict(
        detector=detector,
        severity="high",
        object_name="SOME_OBJECT",
        line=1,
        snippet="x",
        message="m",
        source_file="oracle.sql",
        group_key="abc123",
    )
    base.update(overrides)
    return base


def _finding(detector: str, **overrides) -> Finding:
    base = dict(
        detector=detector,
        severity="high",
        object_name="SOME_OBJECT",
        line=1,
        snippet="x",
        message="m",
        source_file="generated.sql",
    )
    base.update(overrides)
    return Finding(**base)


def test_every_real_detector_has_a_verification_mode():
    on_disk = {
        os.path.basename(f)[:-3]
        for f in glob.glob("ora2pg_gap_report/detectors/*.py")
        if not f.endswith("__init__.py")
    }
    assert on_disk == set(VERIFICATION_MODE)


def test_verbatim_detector_still_present_when_repeated_in_post_migration_scan():
    baseline = [_baseline_record("cross_apply")]
    post = [_finding("cross_apply")]
    results = verify_against_baseline(baseline, post)
    assert len(results) == 1
    assert results[0] == DetectorVerification(
        detector="cross_apply", gap_number="022", baseline_count=1, post_migration_count=1,
        status="still_present",
    )


def test_verbatim_detector_not_detected_when_absent_from_post_migration_scan():
    baseline = [_baseline_record("cross_apply")]
    results = verify_against_baseline(baseline, [])
    assert len(results) == 1
    assert results[0].status == "not_detected"
    assert results[0].post_migration_count == 0


def test_not_verifiable_detector_is_always_not_verifiable_even_if_somehow_redetected():
    # read_only_table drops the flagged construct from ora2pg's output by
    # construction -- but even if some unrelated file coincidentally
    # matched the same detector post-migration, the status must stay
    # not_verifiable, not flip to "still_present". The classification is
    # about whether the *check itself* is meaningful, not about whether
    # findings happen to exist.
    baseline = [_baseline_record("read_only_table")]
    post = [_finding("read_only_table")]
    results = verify_against_baseline(baseline, post)
    assert len(results) == 1
    assert results[0].status == "not_verifiable"


def test_not_verifiable_detector_with_no_post_migration_findings():
    baseline = [_baseline_record("table_partitioning")]
    results = verify_against_baseline(baseline, [])
    assert results[0].status == "not_verifiable"


def test_gap_number_is_none_for_a_detector_with_no_registered_gap():
    baseline = [_baseline_record("dbms_utl_calls")]
    results = verify_against_baseline(baseline, [])
    assert results[0].gap_number is None


def test_baseline_count_reflects_how_many_findings_that_detector_had():
    baseline = [
        _baseline_record("cross_apply", object_name="A"),
        _baseline_record("cross_apply", object_name="B"),
        _baseline_record("cross_apply", object_name="C"),
    ]
    results = verify_against_baseline(baseline, [])
    assert results[0].baseline_count == 3


def test_post_migration_count_reflects_how_many_findings_this_detector_produced_now():
    baseline = [_baseline_record("cross_apply")]
    post = [_finding("cross_apply", object_name="A"), _finding("cross_apply", object_name="B")]
    results = verify_against_baseline(baseline, post)
    assert results[0].post_migration_count == 2
    assert results[0].status == "still_present"


def test_results_cover_every_distinct_detector_in_the_baseline_sorted_by_name():
    baseline = [_baseline_record("json_table"), _baseline_record("cross_apply")]
    results = verify_against_baseline(baseline, [])
    assert [r.detector for r in results] == ["cross_apply", "json_table"]


def test_post_migration_findings_for_a_detector_not_in_the_baseline_are_ignored():
    # A detector that fires post-migration but was never in the baseline
    # isn't a "verification" result at all -- it's a new, unrelated
    # finding, out of scope for this comparison (the normal scan report
    # already covers it).
    baseline = [_baseline_record("cross_apply")]
    post = [_finding("cross_apply"), _finding("pivot_clause")]
    results = verify_against_baseline(baseline, post)
    assert [r.detector for r in results] == ["cross_apply"]


def test_unknown_detector_defaults_to_not_verifiable():
    # A third-party detector with no VERIFICATION_MODE entry (added
    # directly via terminal_report.py rather than through cli.py's
    # registered list) must not be silently treated as verbatim -- an
    # unrecognized detector defaults to the conservative option.
    baseline = [_baseline_record("some_third_party_detector")]
    post = [_finding("some_third_party_detector")]
    results = verify_against_baseline(baseline, post)
    assert results[0].status == "not_verifiable"
