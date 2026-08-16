"""Registry consistency check ("doctor"): for every GAP-NNN in
ora2pg_gap_report/gap_registry.py, verifies that everything this
project's own evidentiary standard requires actually exists on disk --
a research doc, the detector module, and a test file with at least one
positive test and at least one guard/negative test.

This doesn't re-verify *content* (that a research doc's claimed ora2pg
output is real, that a detector's severity reasoning holds up) -- that's
what docs/research/AUDIT.md and each gap's own doc are for, checked by
hand against a real ora2pg + PostgreSQL. This only catches drift: a gap
added to gap_registry.py without one of its required artifacts actually
being there, or a test file that only guards against false positives
without ever proving the detector fires on a real positive case. That's
exactly the class of problem previous AUDIT.md review rounds in this
project kept finding by hand -- stale test counts, a gap missing a
negative-case test -- this makes it a rerunnable check instead of
something that has to be rediscovered by rereading everything.

Run: python3 scripts/doctor.py
Exit code: 0 if every gap's artifacts check out, 1 if any is missing.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_gap_test_counts import count_tests  # noqa: E402
from ora2pg_gap_report.gap_registry import GAPS, research_doc_path  # noqa: E402

# Matches a detector filename one level under 'detectors/' in the ASCII
# tree README.md draws in its "Архитектура" section, e.g.
# '│   ├── autonomous_tx.py        # PRAGMA ...' or the tree's last entry
# ('│   └── identity_column.py ...'). Deliberately requires the '│   '
# prefix (one level of indentation under detectors/) so a *sibling* of
# detectors/ at the same tree depth as detectors/ itself (cli.py,
# effort_estimator.py, ...) is never mistaken for a detector module.
_README_DETECTOR_RE = re.compile(r"^│\s+(?:├──|└──)\s+([a-z_]+)\.py", re.MULTILINE)


def _detector_names_on_disk() -> set[str]:
    detectors_dir = REPO_ROOT / "ora2pg_gap_report" / "detectors"
    return {p.stem for p in detectors_dir.glob("*.py") if p.stem != "__init__"}


def _detector_names_in_readme() -> set[str]:
    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    return set(_README_DETECTOR_RE.findall(readme_text))


def check_gap(gap) -> list[str]:
    prefix = f"GAP-{gap.number}"
    problems = []

    if research_doc_path(gap) is None:
        problems.append(
            f"{prefix}: research-документ не найден (docs/research/gap-{gap.number}-{gap.slug}.md)"
        )

    detector_path = REPO_ROOT / "ora2pg_gap_report" / "detectors" / f"{gap.detector}.py"
    if not detector_path.is_file():
        problems.append(f"{prefix}: детектор не найден ({detector_path.relative_to(REPO_ROOT)})")

    missing_test_files = [tf for tf in gap.test_files if not (REPO_ROOT / "tests" / tf).is_file()]
    for tf in missing_test_files:
        problems.append(f"{prefix}: тестовый файл не найден (tests/{tf})")

    if not missing_test_files:
        total, guards = count_tests(gap.test_files)
        if total == 0:
            problems.append(f"{prefix}: нет ни одного теста")
        elif total <= guards:
            problems.append(f"{prefix}: нет ни одного позитивного теста (только guard-тесты)")
        elif guards == 0:
            problems.append(f"{prefix}: нет ни одного guard-теста (нет проверки на ложные срабатывания)")

    return problems


def check_readme_parity() -> list[str]:
    """The 'Архитектура' section's file tree in README.md must list
    exactly the detector modules that actually exist on disk -- neither
    more (a stale entry for a module that was renamed/removed) nor fewer
    (a new detector added to ora2pg_gap_report/detectors/ but never
    mentioned in README.md, silently making the README's own detector
    count/description wrong the moment a reader trusts it). Found and
    fixed once already, by hand, after the section drifted for several
    releases -- this makes that specific class of drift a rerunnable
    check instead of something that has to be rediscovered by rereading
    the whole README."""
    on_disk = _detector_names_on_disk()
    in_readme = _detector_names_in_readme()

    problems = []
    for name in sorted(on_disk - in_readme):
        problems.append(
            f"README.md: детектор '{name}.py' существует, но не упомянут в файловом "
            "дереве секции «Архитектура»"
        )
    for name in sorted(in_readme - on_disk):
        problems.append(
            f"README.md: секция «Архитектура» упоминает '{name}.py', "
            "но такого файла нет в ora2pg_gap_report/detectors/"
        )
    return problems


def main() -> int:
    print(f"Проверено {len(GAPS)} gap'ов из реестра (ora2pg_gap_report/gap_registry.py).\n")

    all_problems: list[str] = []
    for gap in GAPS:
        all_problems.extend(check_gap(gap))
    all_problems.extend(check_readme_parity())

    if not all_problems:
        print(
            "✓ Всё чисто: у каждого gap'а есть research-документ, детектор, позитивный и "
            "guard-тест, и README.md не разошёлся со списком детекторов на диске."
        )
        return 0

    print(f"✗ Найдено {len(all_problems)} проблем:\n")
    for problem in all_problems:
        print(f"  {problem}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
