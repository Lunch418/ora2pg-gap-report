from src.effort_estimator import estimate_hours, summarize_by_severity
from src.models import Finding


def _finding(severity: str) -> Finding:
    return Finding(
        detector="x", severity=severity, object_name="X.Y", line=1, snippet="", message=""
    )


def test_estimate_hours_sums_ranges_per_severity():
    findings = [_finding("high"), _finding("medium"), _finding("low")]
    lo, hi = estimate_hours(findings)
    assert lo == 2.0 + 1.0 + 0.25
    assert hi == 8.0 + 4.0 + 1.0


def test_estimate_hours_empty_list_is_zero():
    assert estimate_hours([]) == (0.0, 0.0)


def test_summarize_by_severity_counts_each_bucket():
    findings = [_finding("high"), _finding("high"), _finding("low")]
    assert summarize_by_severity(findings) == {"high": 2, "medium": 0, "low": 1}


def test_summarize_by_severity_buckets_unknown_severities_as_other():
    findings = [_finding("high"), _finding("critical")]
    counts = summarize_by_severity(findings)
    assert counts == {"high": 1, "medium": 0, "low": 0, "other": 1}
    assert sum(counts.values()) == len(findings)
