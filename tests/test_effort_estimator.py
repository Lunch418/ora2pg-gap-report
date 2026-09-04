from ora2pg_gap_report.effort_estimator import (
    distinct_detector_count,
    estimate_hours,
    ordered_counts,
    summarize_by_severity,
)
from ora2pg_gap_report.models import Finding


def _finding(severity: str, detector: str = "x") -> Finding:
    return Finding(
        detector=detector, severity=severity, object_name="X.Y", line=1, snippet="", message_id="read_only_table"
    )


def test_estimate_hours_sums_full_ranges_for_distinct_detectors():
    # Each of these is the *first* (and only) finding for its own
    # detector, so each is priced at that detector's own full severity
    # range -- no repeat-occurrence discount applies here.
    findings = [_finding("high", "a"), _finding("medium", "b"), _finding("low", "c")]
    lo, hi = estimate_hours(findings)
    assert lo == 2.0 + 1.0 + 0.25
    assert hi == 8.0 + 4.0 + 1.0


def test_estimate_hours_prices_only_the_first_occurrence_of_a_detector_at_full_range():
    # Eight findings from the same detector are one diagnosed fix pattern
    # applied eight times, not eight independent high-severity problems --
    # only the first is priced at the high range, the other seven at the
    # flat repeat-occurrence range.
    findings = [_finding("high", "autonomous_tx") for _ in range(8)]
    lo, hi = estimate_hours(findings)
    assert lo == 2.0 + 7 * 0.25
    assert hi == 8.0 + 7 * 1.0


def test_estimate_hours_repeat_range_is_independent_of_severity():
    findings = [_finding("high", "d"), _finding("high", "d")]
    lo, hi = estimate_hours(findings)
    # first: high range (2, 8); second (repeat, same detector): (0.25, 1),
    # not another (2, 8) -- the repeat range doesn't scale with severity.
    assert lo == 2.0 + 0.25
    assert hi == 8.0 + 1.0


def test_estimate_hours_tracks_repeats_independently_per_detector():
    findings = [
        _finding("high", "a"),
        _finding("high", "a"),  # a's 2nd -- repeat range
        _finding("medium", "b"),
        _finding("medium", "b"),  # b's 2nd -- repeat range
        _finding("medium", "b"),  # b's 3rd -- repeat range
    ]
    lo, hi = estimate_hours(findings)
    assert lo == (2.0 + 0.25) + (1.0 + 0.25 + 0.25)
    assert hi == (8.0 + 1.0) + (4.0 + 1.0 + 1.0)


def test_estimate_hours_empty_list_is_zero():
    assert estimate_hours([]) == (0.0, 0.0)


def test_distinct_detector_count_counts_unique_detectors_not_findings():
    findings = [_finding("high", "a"), _finding("high", "a"), _finding("medium", "b")]
    assert distinct_detector_count(findings) == 2
    assert len(findings) == 3


def test_distinct_detector_count_empty_list_is_zero():
    assert distinct_detector_count([]) == 0


def test_summarize_by_severity_counts_each_bucket():
    findings = [_finding("high"), _finding("high"), _finding("low")]
    assert summarize_by_severity(findings) == {"high": 2, "medium": 0, "low": 1}


def test_summarize_by_severity_buckets_unknown_severities_as_other():
    findings = [_finding("high"), _finding("critical")]
    counts = summarize_by_severity(findings)
    assert counts == {"high": 1, "medium": 0, "low": 0, "other": 1}
    assert sum(counts.values()) == len(findings)


def test_ordered_counts_orders_high_medium_low_first():
    counts = {"high": 0, "medium": 3, "low": 5}
    assert ordered_counts(counts) == [("medium", 3), ("low", 5)]


def test_ordered_counts_appends_other_buckets_after_the_standard_three():
    counts = {"high": 1, "medium": 0, "low": 0, "other": 2}
    assert ordered_counts(counts) == [("high", 1), ("other", 2)]
