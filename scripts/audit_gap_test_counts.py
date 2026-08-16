"""Recompute the per-GAP test counts in docs/research/AUDIT.md's summary
table, so those numbers stay a falsifiable, re-runnable claim instead of
something the reader has to trust or reverse-engineer.

A test is classified as a "guard" (false-positive-avoidance) test if its
body contains `== []` -- i.e. it asserts that on this specific input, the
detector finds nothing. This is a proxy, not a semantic analysis: it will
miss a guard test written as `assert len(findings) == 0` in an unusual
style, and it can't tell a guard test from a positive test that happens to
also contain the literal substring `== []` in an unrelated assertion or
comment. In practice, every test file in this project follows the
established `assert find_x(source) == []` convention for its guard tests
(see any tests/test_*.py for the pattern), so this proxy matches manual
inspection exactly as of the last time this script and docs/research/
AUDIT.md were updated together.

Run: python3 scripts/audit_gap_test_counts.py

The (GAP number, detector, test files) rows this recomputes against live
here: ora2pg_gap_report/gap_registry.py -- this script imports GAPS from
there rather than keeping its own second copy, so there's exactly one
place that data can drift out of sync with reality, not two.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ora2pg_gap_report.gap_registry import GAPS  # noqa: E402

_TEST_DEF_RE = re.compile(r"^def (test_\w+)", re.MULTILINE)
_EMPTY_RESULT_RE = re.compile(r"==\s*\[\]|assert\s+len\([^)]*\)\s*==\s*0")


def count_tests(test_files: tuple[str, ...]) -> tuple[int, int]:
    total = 0
    guards = 0
    for fname in test_files:
        text = (REPO_ROOT / "tests" / fname).read_text()
        parts = _TEST_DEF_RE.split(text)[1:]  # [name, body, name, body, ...]
        for i in range(0, len(parts), 2):
            total += 1
            if _EMPTY_RESULT_RE.search(parts[i + 1]):
                guards += 1
    return total, guards


def main() -> None:
    print(f"{'GAP':<5} {'detector':<22} {'total':>5} {'guards':>7}")
    for gap in GAPS:
        total, guards = count_tests(gap.test_files)
        print(f"{gap.number:<5} {gap.detector:<22} {total:>5} {guards:>7}")


if __name__ == "__main__":
    main()
