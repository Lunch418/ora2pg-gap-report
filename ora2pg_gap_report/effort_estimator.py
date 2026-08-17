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

# What a *second* (and every further) finding from a detector already
# seen elsewhere in the same scan costs, instead of that detector's own
# _HOURS_BY_SEVERITY range again. Rationale: _HOURS_BY_SEVERITY prices
# the expensive part of a fix -- understanding the construct, deciding
# how to rewrite it, checking the result -- which is paid once per
# *pattern*, not once per occurrence. Eight `autonomous_tx` findings in
# one package aren't eight independent design problems; they're the same
# already-diagnosed dblink-wrapper fix applied eight times, and pricing
# each one at the full high-severity range (as a plain per-finding sum
# did before this) inflates the total roughly in proportion to how
# repetitive the codebase happens to be, not to how much genuinely new
# work is in it. This range is deliberately flat across severities
# (unlike _HOURS_BY_SEVERITY) -- re-applying an already-understood fix to
# another occurrence is mostly mechanical find-and-apply work, and that
# part doesn't scale with how architecturally serious the original
# pattern was. Just as uncalibrated as everything else here -- seeding it
# with anything other than a small round number would be pretending to a
# precision this project doesn't have evidence for.
_REPEAT_OCCURRENCE_RANGE: tuple[float, float] = (0.25, 1.0)


def estimate_hours(findings: list[Finding]) -> tuple[float, float]:
    """Sum of per-finding hour ranges, except only the *first* finding
    for each distinct detector is priced at that detector's full
    _HOURS_BY_SEVERITY range -- every later finding from the same
    detector is priced at the flat _REPEAT_OCCURRENCE_RANGE instead. A
    range, not a point estimate — do not collapse it to an average and
    quote that as a number; the spread itself is the honest part of the
    answer. See distinct_detector_count() for the occurrence-vs-pattern
    split this is built on."""
    seen_detectors: set[str] = set()
    total_low = total_high = 0.0
    for f in findings:
        if f.detector in seen_detectors:
            lo, hi = _REPEAT_OCCURRENCE_RANGE
        else:
            seen_detectors.add(f.detector)
            lo, hi = _HOURS_BY_SEVERITY.get(f.severity, _DEFAULT_RANGE)
        total_low += lo
        total_high += hi
    return total_low, total_high


def distinct_detector_count(findings: list[Finding]) -> int:
    """How many distinct detectors fired -- i.e. how many genuinely
    different fix patterns are behind `findings`, as opposed to
    len(findings)'s raw occurrence count. Exists so callers can show that
    split alongside estimate_hours()'s total (e.g. "28 находок, 3
    паттерна") instead of the hour range alone looking like it scales
    linearly with the finding count when it deliberately doesn't."""
    return len({f.detector for f in findings})


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
