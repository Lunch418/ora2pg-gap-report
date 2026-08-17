from .models import Finding

# Deliberately a range per severity, not a single number, and deliberately
# not lines-of-code-weighted: this is an uncalibrated heuristic, not a
# measurement. See README.md, "Почему почти всё high" — presenting a
# fake-precise number here is a trust risk with exactly the audience this
# tool is for. Calibrate against real migration outcomes before treating
# these as commitments.
_HOURS_BY_SEVERITY: dict[str, tuple[float, float]] = {
    "high": (2.0, 8.0),
    "medium": (1.0, 4.0),
    "low": (0.25, 1.0),
}
_DEFAULT_RANGE = (1.0, 4.0)
_SEVERITY_ORDER = ("high", "medium", "low")


def estimate_hours(findings: list[Finding]) -> tuple[float, float]:
    """Sum of per-finding (low, high) hour ranges. A range, not a point
    estimate — do not collapse it to an average and quote that as a
    number; the spread itself is the honest part of the answer."""
    total_low = total_high = 0.0
    for f in findings:
        lo, hi = _HOURS_BY_SEVERITY.get(f.severity, _DEFAULT_RANGE)
        total_low += lo
        total_high += hi
    return total_low, total_high


def summarize_by_severity(findings: list[Finding]) -> dict[str, int]:
    """Counts always sum to len(findings): an unrecognized severity value
    (should not happen with the detectors in this repo today, but nothing
    enforces it at the type level) lands in "other" instead of silently
    vanishing from the displayed total."""
    counts = {"high": 0, "medium": 0, "low": 0}
    other = 0
    for f in findings:
        if f.severity in counts:
            counts[f.severity] += 1
        else:
            other += 1
    if other:
        counts["other"] = other
    return counts


def ordered_counts(counts: dict[str, int]) -> list[tuple[str, int]]:
    """(name, count) pairs ordered high/medium/low first, then any other
    bucket — shared so cli.py's Markdown header and terminal_report.py's
    summary panel present the same ordering instead of each composing it
    independently (and, before this, inconsistently: the Markdown header
    used to fall back to plain dict order)."""
    ordered = [(sev, counts[sev]) for sev in _SEVERITY_ORDER if counts.get(sev)]
    ordered += [(name, n) for name, n in counts.items() if name not in _SEVERITY_ORDER and n]
    return ordered
