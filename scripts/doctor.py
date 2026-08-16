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

Also checks that docs/ARCHITECTURE.md's detector file tree hasn't drifted
from ora2pg_gap_report/detectors/ on disk -- the same class of staleness
that once left README.md (where this section originally lived) describing
a four-detector architecture long after the project had 28. And that
docs/research/GAP_REGISTRY.md's ora2pg/PostgreSQL version columns match
gap_registry.py's own ora2pg_version/postgresql_version fields -- the
Python fields are the canonical source (see GapEntry's own docstring),
the Markdown table is a human-facing restatement of the same facts, and
restated facts drift from their source exactly the way this whole script
exists to catch.

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
# tree docs/ARCHITECTURE.md draws under its "Файловая структура" section,
# e.g. '│   ├── autonomous_tx.py        # PRAGMA ...' or the tree's last
# entry ('│   └── identity_column.py ...').
_TREE_ENTRY_RE = re.compile(r"^│\s+(?:├──|└──)\s+([a-z_]+)\.py")
_DETECTORS_LINE_RE = re.compile(r"^├── detectors/\s*$")

# Matches a GAP_REGISTRY.md table row's number/ora2pg-version/postgresql-
# version columns, e.g.
# '| GAP-001 | ... | `autonomous_tx` | confirmed | 25.0 | 16 | [gap-001](...) |'.
# Anchored on '| confirmed |' specifically (not just any two version-
# shaped columns) so a future non-'confirmed' status row (fixed-upstream/
# wont-fix, both real statuses this table documents) isn't silently
# skipped nor misparsed. Both version columns accept dotted values
# ([\d.]+, not \d+) -- PostgreSQL is "16" today (single-number versioning
# since PG10), but a future gap re-verified against a pre-10 version
# ("9.6") or a specific point release ("16.4") must still be *parsed*
# (even if it wouldn't have a str-equal match), or that row would be
# silently excluded from confirmed_rows entirely and check_gap_registry_
# md_parity() would skip comparing it instead of flagging real drift --
# a digits-only pattern here would fail exactly the way this whole check
# exists to prevent.
_GAP_REGISTRY_ROW_RE = re.compile(r"^\| GAP-(\d{3}) \|.*\| confirmed \| ([\d.]+) \| ([\d.]+) \|", re.MULTILINE)


def _detector_names_on_disk() -> set[str]:
    detectors_dir = REPO_ROOT / "ora2pg_gap_report" / "detectors"
    return {p.stem for p in detectors_dir.glob("*.py") if p.stem != "__init__"}


def _extract_detector_names_from_tree_text(text: str) -> set[str]:
    """Names found in an ASCII tree, but only within the 'detectors/'
    subtree specifically -- not any other '│   ├── x.py'-shaped line
    anywhere in the text. A shape-only match (matching that indentation
    pattern regardless of which subtree it's under) would misparse a
    future, unrelated tree fragment at the same visual depth (e.g. a
    'tests/fixtures/' listing) as claimed detector names, failing the
    build for a change that has nothing to do with detectors."""
    names: set[str] = set()
    in_detectors_subtree = False
    for line in text.splitlines():
        if _DETECTORS_LINE_RE.match(line):
            in_detectors_subtree = True
            continue
        if not in_detectors_subtree:
            continue
        if not line.startswith("│   "):
            break  # first line back out at (or above) detectors/'s own depth
        m = _TREE_ENTRY_RE.match(line)
        if m:
            names.add(m.group(1))
    return names


def _detector_names_in_architecture_doc() -> set[str]:
    doc_text = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    return _extract_detector_names_from_tree_text(doc_text)


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


def check_architecture_doc_parity() -> list[str]:
    """docs/ARCHITECTURE.md's file tree must list exactly the detector
    modules that actually exist on disk -- neither more (a stale entry
    for a module that was renamed/removed) nor fewer (a new detector
    added to ora2pg_gap_report/detectors/ but never mentioned in the
    doc, silently making its own detector count/description wrong the
    moment a reader trusts it). Found and fixed once already, by hand,
    after this exact section (originally in README.md, later moved here)
    drifted for several releases -- this makes that specific class of
    drift a rerunnable check instead of something that has to be
    rediscovered by rereading the whole document."""
    on_disk = _detector_names_on_disk()
    documented = _detector_names_in_architecture_doc()

    problems = []
    for name in sorted(on_disk - documented):
        problems.append(
            f"docs/ARCHITECTURE.md: детектор '{name}.py' существует, но не упомянут в "
            "файловом дереве секции «Файловая структура»"
        )
    for name in sorted(documented - on_disk):
        problems.append(
            f"docs/ARCHITECTURE.md: секция «Файловая структура» упоминает '{name}.py', "
            "но такого файла нет в ora2pg_gap_report/detectors/"
        )
    return problems


def _confirmed_gap_versions_in_text(registry_md_text: str) -> dict[str, tuple[str, str]]:
    return {
        number: (ora2pg_version, postgresql_version)
        for number, ora2pg_version, postgresql_version in _GAP_REGISTRY_ROW_RE.findall(registry_md_text)
    }


def check_gap_registry_md_parity() -> list[str]:
    """docs/research/GAP_REGISTRY.md's ora2pg/PostgreSQL version columns
    must match gap_registry.py's own ora2pg_version/postgresql_version
    fields for every gap the table marks 'confirmed' -- the Python fields
    are the canonical source (GapEntry's own docstring says so), the
    table is a human-facing restatement, and this only flags an actual
    mismatch between the two, not a missing row: a gap the table marks
    'fixed-upstream'/'wont-fix' instead of 'confirmed' is deliberately
    not compared here, since neither of those statuses is tracked in
    gap_registry.py at all -- there's nothing to compare it against, and
    reporting that as a "drift" would be a false positive on a real,
    intentional status change."""
    registry_md = (REPO_ROOT / "docs" / "research" / "GAP_REGISTRY.md").read_text(encoding="utf-8")
    confirmed_rows = _confirmed_gap_versions_in_text(registry_md)

    problems = []
    for gap in GAPS:
        if gap.number not in confirmed_rows:
            continue
        row_ora2pg, row_postgresql = confirmed_rows[gap.number]
        if row_ora2pg != gap.ora2pg_version or row_postgresql != gap.postgresql_version:
            problems.append(
                f"GAP-{gap.number}: docs/research/GAP_REGISTRY.md указывает ora2pg "
                f"{row_ora2pg}/PostgreSQL {row_postgresql}, а gap_registry.py — ora2pg "
                f"{gap.ora2pg_version}/PostgreSQL {gap.postgresql_version}"
            )
    return problems


def main() -> int:
    print(f"Проверено {len(GAPS)} gap'ов из реестра (ora2pg_gap_report/gap_registry.py).\n")

    all_problems: list[str] = []
    for gap in GAPS:
        all_problems.extend(check_gap(gap))
    all_problems.extend(check_architecture_doc_parity())
    all_problems.extend(check_gap_registry_md_parity())

    if not all_problems:
        print(
            "✓ Всё чисто: у каждого gap'а есть research-документ, детектор, позитивный и "
            "guard-тест, docs/ARCHITECTURE.md не разошёлся со списком детекторов на диске, "
            "и версии в GAP_REGISTRY.md совпадают с gap_registry.py."
        )
        return 0

    print(f"✗ Найдено {len(all_problems)} проблем:\n")
    for problem in all_problems:
        print(f"  {problem}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
