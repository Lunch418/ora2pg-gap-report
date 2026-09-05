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
exists to catch. And that every message_id a detector emits has both
translations in messages.py, and that every entry in messages.py is
reachable from some detector -- drift in the first direction crashes the
renderer on a real finding, drift in the second leaves dead text that
still reads as a live translation. Plus the same coverage check for
messages.py's REMEDIATION_HINTS, without which --lang en silently falls
back to Russian for a new or edited detector.
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

And that no English translation in i18n.py contains a word glued together
out of two by Python's implicit string concatenation -- writing a long
message as adjacent literals silently drops the separating space whenever
a line ends mid-sentence without one ("an" + "object type" -> "anobject
type"). That class of typo is invisible to every other check here (the
translation exists, it's just malformed), and it really did ship once in
this project before this check existed.

And that every gap's `severity` is a real value and matches the literal
severity="..." string the detector's own source actually uses -- this
was the one gap-level fact that had no cross-check against reality at
all before: nothing previously would have noticed if gap_registry.py's
claimed severity for a detector drifted from what a later edit to that
detector's own code actually emits.

Run: python3 scripts/doctor.py
Exit code: 0 if every gap's artifacts check out, 1 if any is missing.
"""

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_gap_test_counts import count_tests  # noqa: E402
from ora2pg_gap_report import messages  # noqa: E402
from ora2pg_gap_report.core import detector_names  # noqa: E402
from ora2pg_gap_report.gap_registry import (  # noqa: E402
    FAILURE_STAGE_EXEMPT_DETECTORS,
    FAILURE_STAGES,
    GAPS,
    GapEntry,
    research_doc_path,
)
from ora2pg_gap_report.verification import VERIFICATION_MODE  # noqa: E402

# Matches a detector filename one level under 'detectors/' in the ASCII
# tree docs/ARCHITECTURE.md draws under its "Файловая структура" section,
# e.g. '│   ├── autonomous_tx.py        # PRAGMA ...' or the tree's last
# entry ('│   └── identity_column.py ...').
_TREE_ENTRY_RE = re.compile(r"^│\s+(?:├──|└──)\s+([a-z_]+)\.py")
_DETECTORS_LINE_RE = re.compile(r"^├── detectors/\s*$")

# Matches a GAP_REGISTRY.md table row's number/severity/ora2pg-version/
# postgresql-version columns, e.g.
# '| GAP-001 | ... | `autonomous_tx` | high | confirmed | 25.0 | 16 | [gap-001](...) |'.
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
_GAP_REGISTRY_ROW_RE = re.compile(
    r"^\| GAP-(\d{3}) \|.*\| (high|medium|low) \| confirmed \| ([\d.]+) \| ([\d.]+) \|", re.MULTILINE
)

# Matches a `severity="high"`-shaped literal anywhere in a detector's own
# source text -- used to cross-check GapEntry.severity against what the
# detector's Finding(...) calls actually emit, not just what the registry
# claims. VALID_SEVERITIES is the same three values models.Finding's own
# `severity` field comment documents; kept here rather than imported, since
# Finding doesn't expose them as a checkable collection of its own.
_SEVERITY_LITERAL_RE = re.compile(r'severity="(high|medium|low)"')
VALID_SEVERITIES = ("high", "medium", "low")


def _detector_names_on_disk() -> set[str]:
    detectors_dir = REPO_ROOT / "ora2pg_gap_report" / "detectors"
    return {p.stem for p in detectors_dir.glob("*.py") if p.stem != "__init__"}


def _str_constant(node: ast.AST) -> str | None:
    """The value of `node` if it is a string literal, else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _message_ids_in(detector: str) -> list[str]:
    """Every message_id the detector `detector` can emit, read out of its
    own source.

    Read, not imported and called: a detector's message_id is a literal --
    either in a Finding(...) it constructs by hand, or in the DetectorSpec
    it declares -- and running the detector to find out which ids it emits
    would need a source file that happens to trigger each one. The literal
    is what ships, so the literal is what gets checked.

    Both detector forms are read, because both exist on purpose. A
    hand-written detector passes `message_id=` to Finding directly. A
    spec-built one usually passes nothing, and DetectorSpec then resolves
    the id to the detector's own name -- so this reads the spec's `name=`
    in exactly the case DetectorSpec.resolved_message_id would fall back
    to it. Reading only the explicit keyword, as this did before the
    factory existed, made every migrated detector look like it emitted no
    message at all, and its live MESSAGES entry look like an orphan.
    """
    path = REPO_ROOT / "ora2pg_gap_report" / "detectors" / f"{detector}.py"
    ids: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.keyword) and node.arg == "message_id":
            explicit = _str_constant(node.value)
            if explicit is not None:
                ids.append(explicit)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "DetectorSpec"
            and not any(kw.arg == "message_id" for kw in node.keywords)
        ):
            for kw in node.keywords:
                if kw.arg == "name":
                    implied = _str_constant(kw.value)
                    if implied is not None:
                        ids.append(implied)
    return ids


def _detector_message_ids() -> dict[str, str]:
    """{detector: message_id} for every detector that emits exactly one.

    A detector emitting more than one id (bulk_collect has three) is
    represented by whichever _message_ids_in() reports first -- every id
    it uses is validated anyway by check_messages_cover_every_detector()
    below, which walks MESSAGES from the other direction."""
    found: dict[str, str] = {}
    for name in sorted(_detector_names_on_disk()):
        ids = _message_ids_in(name)
        if ids:
            found[name] = ids[0]
    return found


def check_messages_cover_every_detector() -> list[str]:
    """Every message_id literal in every detector exists in MESSAGES, and
    every MESSAGES entry is actually reachable from some detector.

    The second direction matters as much as the first: an id left behind
    after a detector was renamed or deleted is dead weight that still
    reads as a live translation, and it is exactly the kind of thing
    nobody notices without a check, because nothing breaks."""
    used: set[str] = set()
    problems = []
    for name in sorted(_detector_names_on_disk()):
        for mid in _message_ids_in(name):
            used.add(mid)
            if mid not in messages.MESSAGES:
                problems.append(
                    f"{name}.py: message_id '{mid}' is not in messages.MESSAGES"
                )
    for orphan in sorted(set(messages.MESSAGES) - used):
        problems.append(
            f"messages.py: MESSAGES['{orphan}'] is not referenced by any detector"
        )
    return problems


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


def _confirmed_gap_versions_in_text(registry_md_text: str) -> dict[str, tuple[str, str, str]]:
    return {
        number: (severity, ora2pg_version, postgresql_version)
        for number, severity, ora2pg_version, postgresql_version in _GAP_REGISTRY_ROW_RE.findall(
            registry_md_text
        )
    }


def check_gap_registry_md_parity() -> list[str]:
    """docs/research/GAP_REGISTRY.md's Severity/ora2pg/PostgreSQL columns
    must match gap_registry.py's own severity/ora2pg_version/
    postgresql_version fields for every gap the table marks 'confirmed'
    -- the Python fields are the canonical source (GapEntry's own
    docstring says so), the table is a human-facing restatement, and
    this only flags an actual mismatch between the two, not a missing
    row: a gap the table marks 'fixed-upstream'/'wont-fix' instead of
    'confirmed' is deliberately not compared here, since neither of
    those statuses is tracked in gap_registry.py at all -- there's
    nothing to compare it against, and reporting that as a "drift" would
    be a false positive on a real, intentional status change."""
    registry_md = (REPO_ROOT / "docs" / "research" / "GAP_REGISTRY.md").read_text(encoding="utf-8")
    confirmed_rows = _confirmed_gap_versions_in_text(registry_md)

    problems = []
    for gap in GAPS:
        if gap.number not in confirmed_rows:
            continue
        row_severity, row_ora2pg, row_postgresql = confirmed_rows[gap.number]
        if row_severity != gap.severity:
            problems.append(
                f"GAP-{gap.number}: docs/research/GAP_REGISTRY.md указывает severity "
                f"'{row_severity}', а gap_registry.py — '{gap.severity}'"
            )
        if row_ora2pg != gap.ora2pg_version or row_postgresql != gap.postgresql_version:
            problems.append(
                f"GAP-{gap.number}: docs/research/GAP_REGISTRY.md указывает ora2pg "
                f"{row_ora2pg}/PostgreSQL {row_postgresql}, а gap_registry.py — ora2pg "
                f"{gap.ora2pg_version}/PostgreSQL {gap.postgresql_version}"
            )
    return problems


def check_i18n_translations_parity() -> list[str]:
    """Every message_id a detector actually emits must exist in
    messages.MESSAGES with both languages filled in, and every detector
    on disk must have a REMEDIATION_HINTS entry with both filled in too.

    The failure mode this guards changed shape when messages moved into
    their own registry. It used to be silent: a message keyed by its own
    Russian text fell back to Russian under --lang en the moment anyone
    edited that text. Now an unknown id raises instead, so the risk is a
    loud crash rather than a quiet wrong language -- but a *blank* or
    missing translation is still silent, and a detector wired to an id
    nobody added is still a bug worth catching before it ships rather
    than on a user's first scan."""
    problems = []
    for detector, message_id in sorted(_detector_message_ids().items()):
        message = messages.MESSAGES.get(message_id)
        if message is None:
            problems.append(
                f"messages.py: detector '{detector}' emits message_id "
                f"'{message_id}', which is not in MESSAGES (any finding from "
                "it would crash the renderer)"
            )
            continue
        for lang_name, value in (("ru", message.ru), ("en", message.en)):
            if not value.strip():
                problems.append(
                    f"messages.py: MESSAGES['{message_id}'].{lang_name} is empty"
                )
    # Hints are keyed by detector, not by message id: a detector emitting
    # three messages still gets one line of advice.
    for name in sorted(_detector_names_on_disk()):
        hint = messages.REMEDIATION_HINTS.get(name)
        if hint is None:
            problems.append(f"messages.py: REMEDIATION_HINTS has no entry for '{name}'")
            continue
        for lang_name, value in (("ru", hint.ru), ("en", hint.en)):
            if not value.strip():
                problems.append(
                    f"messages.py: REMEDIATION_HINTS['{name}'].{lang_name} is empty"
                )
    for orphan in sorted(set(messages.REMEDIATION_HINTS) - _detector_names_on_disk()):
        problems.append(
            f"messages.py: REMEDIATION_HINTS['{orphan}'] names no detector on disk"
        )
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
    actually be in one of core.py's per-dialect detector tuples
    (_ORACLE_DETECTORS, _MYSQL_DETECTORS, ...) -- a detector module that
    exists, is registered in gap_registry.py/verification.py/i18n.py, and
    has passing tests, but was never added to its dialect's tuple would
    still never actually run during a real scan_source() call. Nothing
    else in this project's own test suite catches that specific failure
    mode in general (a positive test calls find_xxx(source) directly,
    bypassing the scan loop entirely; a real-corpus test like
    test_scan_source_runs_all_detectors_on_logger only catches it for
    whichever detectors that one fixture happens to trigger).

    detector_names() with no dialect argument returns the union across
    every dialect's own tuple (see its own docstring), so this check
    covers a MySQL detector left out of _MYSQL_DETECTORS exactly the same
    way it always covered an Oracle one left out of _ORACLE_DETECTORS."""
    on_disk = _detector_names_on_disk() - {"connect_by"}
    in_scan_loop = set(detector_names())
    problems = []
    for name in sorted(on_disk - in_scan_loop):
        problems.append(
            f"core.py: детектор '{name}' есть на диске, но не добавлен ни в один "
            "диалект -- никогда не выполняется при обычном сканировании"
        )
    for name in sorted(in_scan_loop - on_disk):
        problems.append(
            f"core.py: детектор '{name}' зарегистрирован в одном из диалектов, но "
            "такого файла нет в ora2pg_gap_report/detectors/"
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


# A run of letters this long is a glued-together pair in ordinary prose --
# no real English or Russian word in these messages reaches it. Deliberately
# generous: the point is to catch the obvious breakage without flagging
# legitimately long technical terms.
_GLUED_WORD_RE = re.compile(r"[A-Za-z]{18,}")


def check_translations_are_not_glued() -> list[str]:
    """Every English translation must be free of words glued together by
    Python's implicit string concatenation. Writing a long message as a
    run of adjacent literals is the established style in i18n.py, and it
    silently loses the separating space whenever one literal ends a word
    and the next begins one -- 'an' + 'object type' becomes 'anobject
    type'. Nothing else here would notice: the translation is present, so
    check_i18n_translations_parity() passes, and the string is a valid
    Python literal, so nothing fails at import. This exact bug shipped
    once in this project (a batch of translations generated with a
    line-wrapper that stripped the separators), which is why it's now a
    rerunnable check rather than something spotted by reading output."""
    problems = []
    checked: list[tuple[str, dict[str, str]]] = [
        ("REMEDIATION_HINTS.en", {k: v.en for k, v in messages.REMEDIATION_HINTS.items()}),
        ("MESSAGES.ru", {k: v.ru for k, v in messages.MESSAGES.items()}),
        ("MESSAGES.en", {k: v.en for k, v in messages.MESSAGES.items()}),
    ]
    for name, mapping in checked:
        for key, value in mapping.items():
            for word in _GLUED_WORD_RE.findall(value):
                label = key if len(key) < 40 else key[:37] + "..."
                problems.append(
                    f"i18n.py: {name}[{label!r}] содержит склеенное слово "
                    f"'{word}' -- скорее всего потерян пробел на стыке "
                    "соседних строковых литералов"
                )
    return problems


def check_gap_severity_matches_detector_source() -> list[str]:
    """GapEntry.severity must be one of VALID_SEVERITIES, and must match
    what the detector's own source actually emits -- severity had never
    been centralized anywhere before this field existed, so nothing
    previously caught a registry claim drifting from a detector edited
    later (or a typo at the point this field was first filled in for all
    37 gaps by hand). Scans the detector's source text for every
    `severity="..."` literal rather than importing and running the
    detector against a fixture: every detector in this registry was
    confirmed by hand to use exactly one such literal throughout its own
    file (see gap_registry.py's GapEntry.severity docstring), so a plain
    text scan is enough to catch drift without needing a triggering input
    per detector -- the same style check_architecture_doc_parity() already
    uses for the detector file tree, just scanning a .py file instead of a
    .md one. A detector genuinely using more than one severity value would
    make the source-derived set ambiguous rather than wrong -- reported as
    its own, distinct problem, not silently resolved by picking one."""
    problems = []
    for gap in GAPS:
        if gap.severity not in VALID_SEVERITIES:
            problems.append(
                f"GAP-{gap.number} ({gap.detector}): severity='{gap.severity}' "
                f"не из VALID_SEVERITIES ({', '.join(VALID_SEVERITIES)})"
            )
            continue

        detector_path = REPO_ROOT / "ora2pg_gap_report" / "detectors" / f"{gap.detector}.py"
        if not detector_path.is_file():
            continue  # already reported by check_gap()

        source_severities = set(_SEVERITY_LITERAL_RE.findall(detector_path.read_text(encoding="utf-8")))
        if len(source_severities) > 1:
            problems.append(
                f"GAP-{gap.number} ({gap.detector}): исходник детектора использует несколько "
                f"разных severity ({', '.join(sorted(source_severities))}) -- gap_registry.py "
                "не может задать одно значение для всех"
            )
        elif source_severities and source_severities != {gap.severity}:
            (actual,) = source_severities
            problems.append(
                f"GAP-{gap.number} ({gap.detector}): gap_registry.py задаёт severity='{gap.severity}', "
                f"а исходник детектора реально использует severity='{actual}'"
            )
        elif not source_severities:
            problems.append(
                f"GAP-{gap.number} ({gap.detector}): в исходнике детектора не нашлось ни одного "
                "severity=\"...\" литерала для сверки с gap_registry.py"
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
    all_problems.extend(check_messages_cover_every_detector())
    all_problems.extend(check_verification_mode_parity())
    all_problems.extend(check_scan_loop_registration_parity())
    all_problems.extend(check_failure_stage_values())
    all_problems.extend(check_gap_severity_matches_detector_source())
    all_problems.extend(check_translations_are_not_glued())

    if not all_problems:
        print(
            "✓ Всё чисто: у каждого gap'а есть research-документ, детектор, позитивный и "
            "guard-тест, docs/ARCHITECTURE.md не разошёлся со списком детекторов на диске, "
            "версии в GAP_REGISTRY.md совпадают с gap_registry.py, у каждого детектора "
            "оба перевода в messages.py (и текст находки, и совет), у каждого детектора есть запись в "
            "verification.py, каждый детектор с диска реально зарегистрирован в "
            "своём диалекте в core.py, у каждого gap'а (кроме FAILURE_STAGE_EXEMPT_DETECTORS) "
            "задан валидный failure_stage, у каждого gap'а severity в реестре совпадает "
            "с тем, что реально использует исходник детектора, и ни в одном английском "
            "переводе нет слов, склеенных на стыке строковых литералов."
        )
        return 0

    print(f"✗ Найдено {len(all_problems)} проблем:\n")
    for problem in all_problems:
        print(f"  {problem}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
