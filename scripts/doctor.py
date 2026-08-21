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
exists to catch. And that every detector's message constant(s) have an
English translation registered in i18n.py (EXPLANATION_EN/
REMEDIATION_HINT_EN) -- the class of drift that would otherwise leave
--lang en silently falling back to Russian for a new or edited detector.
And that every detector has a verification.py VERIFICATION_MODE entry --
without it, a new detector added to `--verify` would silently default to
NOT_VERIFIABLE (safe, but unnoticed) rather than the classification
actually being made, checked, and recorded on purpose.

And that every detector module on disk (other than connect_by, deliberately
opt-in via --check-connect-by) is actually registered in core.py's
_DETECTORS -- a module that's fully wired into gap_registry.py/
verification.py/i18n.py and has passing tests could otherwise still never
run during a real scan_source() call if it was simply never added to that
tuple; nothing else in this project's own test suite catches that in
general (see check_scan_loop_registration_parity()'s own docstring).

And that every gap's `failure_stage` is one of the defined FAILURE_STAGES
-- a typo'd stage string would otherwise silently fail to render in
--explain rather than error -- and that every gap *has* one, except the
two in FAILURE_STAGE_EXEMPT_DETECTORS (see gap_registry.py's own
docstring and docs/failure-stage-notes.md for why those two are
different in kind, not just unclassified yet).

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
from ora2pg_gap_report import i18n  # noqa: E402
from ora2pg_gap_report.core import detector_names  # noqa: E402
from ora2pg_gap_report.gap_registry import (  # noqa: E402
    FAILURE_STAGE_EXEMPT_DETECTORS,
    FAILURE_STAGES,
    GAPS,
    GapEntry,
    research_doc_path,
)
from ora2pg_gap_report.terminal_report import _REMEDIATION_HINT  # noqa: E402
from ora2pg_gap_report.verification import VERIFICATION_MODE  # noqa: E402

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


def _detector_message_constants() -> list[tuple[str, str, str]]:
    """(module_name, constant_name, value) for every module-level constant
    in ora2pg_gap_report/detectors/*.py whose name contains 'MESSAGE' --
    the same extraction i18n.py's EXPLANATION_EN dict was built from by
    hand. A detector can have more than one (bulk_collect has three)."""
    import importlib

    items = []
    for name in sorted(_detector_names_on_disk()):
        module = importlib.import_module(f"ora2pg_gap_report.detectors.{name}")
        for attr in vars(module):
            if attr.isupper() and "MESSAGE" in attr:
                items.append((name, attr, getattr(module, attr)))
    return items


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


def check_gap(gap: GapEntry) -> list[str]:
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


def check_i18n_translations_parity() -> list[str]:
    """Every detector's message constant(s) must have an English
    translation in i18n.EXPLANATION_EN, and every detector that
    terminal_report.py's _REMEDIATION_HINT covers must have a matching
    entry in i18n.REMEDIATION_HINT_EN -- the same drift the doc/registry
    parity checks above catch, just for the English output path: a
    detector added (or a message string edited) without updating i18n.py
    would otherwise silently fall back to Russian text under --lang en,
    with nothing flagging the gap."""
    problems = []
    for name, attr, message in _detector_message_constants():
        if message not in i18n.EXPLANATION_EN:
            problems.append(
                f"i18n.py: {name}.{attr} has no English translation in EXPLANATION_EN "
                "(--lang en would silently fall back to Russian for this finding)"
            )
    for name in sorted(_REMEDIATION_HINT):
        if name not in i18n.REMEDIATION_HINT_EN:
            problems.append(f"i18n.py: REMEDIATION_HINT_EN is missing an entry for '{name}'")
    return problems


def check_verification_mode_parity() -> list[str]:
    """Every real detector on disk must have a verification.py
    VERIFICATION_MODE entry -- the classification of whether ora2pg
    copies its flagged construct into the generated PostgreSQL output
    verbatim (--verify can meaningfully recheck it) or drops/mangles it
    (--verify can't) is a deliberate, researched decision per detector,
    not something that should silently default for a new one."""
    on_disk = _detector_names_on_disk()
    problems = []
    for name in sorted(on_disk - set(VERIFICATION_MODE)):
        problems.append(
            f"verification.py: детектор '{name}' не имеет записи в VERIFICATION_MODE"
        )
    for name in sorted(set(VERIFICATION_MODE) - on_disk):
        problems.append(
            f"verification.py: VERIFICATION_MODE упоминает '{name}', "
            "но такого файла нет в ora2pg_gap_report/detectors/"
        )
    return problems


def check_scan_loop_registration_parity() -> list[str]:
    """Every detector on disk (other than connect_by, deliberately opt-in
    via --check-connect-by rather than part of the main scan loop) must
    actually be in core.py's _DETECTORS -- a detector module that exists,
    is registered in gap_registry.py/verification.py/i18n.py, and has
    passing tests, but was never added to _DETECTORS would still never
    actually run during a real scan_source() call. Nothing else in this
    project's own test suite catches that specific failure mode in
    general (a positive test calls find_xxx(source) directly, bypassing
    _DETECTORS entirely; a real-corpus test like test_scan_source_runs_
    all_detectors_on_logger only catches it for whichever detectors that
    one fixture happens to trigger)."""
    on_disk = _detector_names_on_disk() - {"connect_by"}
    in_scan_loop = set(detector_names())
    problems = []
    for name in sorted(on_disk - in_scan_loop):
        problems.append(
            f"core.py: детектор '{name}' есть на диске, но не добавлен в _DETECTORS "
            "-- никогда не выполняется при обычном сканировании"
        )
    for name in sorted(in_scan_loop - on_disk):
        problems.append(
            f"core.py: _DETECTORS упоминает '{name}', но такого файла нет в "
            "ora2pg_gap_report/detectors/"
        )
    return problems


def check_failure_stage_values() -> list[str]:
    """A *set* value must be a real one -- catches a typo silently
    producing an unrendered/missing --explain line instead of an error.
    Full coverage is required too, except for the two detectors in
    FAILURE_STAGE_EXEMPT_DETECTORS (autonomous_tx, object_type -- their
    finding isn't a code-shape/runtime problem at all, see that set's own
    docstring): a new gap added later without deciding on a failure_stage
    should fail this check, not silently stay None forever."""
    problems = []
    for gap in GAPS:
        if gap.failure_stage is None:
            if gap.detector not in FAILURE_STAGE_EXEMPT_DETECTORS:
                problems.append(
                    f"GAP-{gap.number} ({gap.detector}): failure_stage не задан и детектор "
                    "не в FAILURE_STAGE_EXEMPT_DETECTORS"
                )
        elif gap.failure_stage not in FAILURE_STAGES:
            problems.append(
                f"GAP-{gap.number} ({gap.detector}): failure_stage='{gap.failure_stage}' "
                f"не из FAILURE_STAGES ({', '.join(FAILURE_STAGES)})"
            )
    return problems


def main() -> int:
    print(f"Проверено {len(GAPS)} gap'ов из реестра (ora2pg_gap_report/gap_registry.py).\n")

    all_problems: list[str] = []
    for gap in GAPS:
        all_problems.extend(check_gap(gap))
    all_problems.extend(check_architecture_doc_parity())
    all_problems.extend(check_gap_registry_md_parity())
    all_problems.extend(check_i18n_translations_parity())
    all_problems.extend(check_verification_mode_parity())
    all_problems.extend(check_scan_loop_registration_parity())
    all_problems.extend(check_failure_stage_values())

    if not all_problems:
        print(
            "✓ Всё чисто: у каждого gap'а есть research-документ, детектор, позитивный и "
            "guard-тест, docs/ARCHITECTURE.md не разошёлся со списком детекторов на диске, "
            "версии в GAP_REGISTRY.md совпадают с gap_registry.py, у каждого детектора "
            "есть английский перевод в i18n.py, у каждого детектора есть запись в "
            "verification.py, каждый детектор с диска реально зарегистрирован в "
            "core._DETECTORS, и у каждого gap'а (кроме FAILURE_STAGE_EXEMPT_DETECTORS) "
            "задан валидный failure_stage."
        )
        return 0

    print(f"✗ Найдено {len(all_problems)} проблем:\n")
    for problem in all_problems:
        print(f"  {problem}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
