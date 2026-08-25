"""Tests for scripts/doctor.py's docs/ARCHITECTURE.md <-> detectors-on-disk
parity check -- the specific class of drift this catches (the file tree's
detector list silently falling behind ora2pg_gap_report/detectors/,
originally in README.md before the docs split) was found and fixed by
hand once already; this makes it a rerunnable check instead of something
that has to be rediscovered by rereading the whole document."""

import dataclasses
import importlib.util
import sys
from pathlib import Path

from ora2pg_gap_report.gap_registry import GapEntry, gap_by_number

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "doctor.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("doctor", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


doctor = _load_module()


def test_extraction_reads_names_from_a_realistic_tree_fragment():
    fragment = (
        "├── detectors/\n"
        "│   ├── autonomous_tx.py        # PRAGMA AUTONOMOUS_TRANSACTION\n"
        "│   ├── with_function.py         # WITH FUNCTION / WITH PROCEDURE\n"
        "│   └── identity_column.py       # last entry, uses the closing branch\n"
        "├── ora2pg_wrapper.py            # not a detector -- sibling of detectors/\n"
        "├── cli.py                      # not a detector either\n"
    )
    names = doctor._extract_detector_names_from_tree_text(fragment)
    assert names == {"autonomous_tx", "with_function", "identity_column"}
    assert "ora2pg_wrapper" not in names
    assert "cli" not in names


def test_extraction_ignores_similarly_indented_lines_outside_the_detectors_subtree():
    # A shape-only match (any '│   ├── x.py'-looking line, regardless of
    # which subtree it's under) would misparse an unrelated future tree
    # fragment at the same visual depth as a claimed detector name.
    fragment = (
        "├── detectors/\n"
        "│   ├── autonomous_tx.py        # PRAGMA AUTONOMOUS_TRANSACTION\n"
        "├── ora2pg_wrapper.py            # breaks out of the detectors/ subtree\n"
        "tests/\n"
        "├── fixtures/\n"
        "│   ├── some_helper.py  # same indentation shape, different subtree entirely\n"
    )
    names = doctor._extract_detector_names_from_tree_text(fragment)
    assert names == {"autonomous_tx"}
    assert "some_helper" not in names


def test_detector_names_on_disk_matches_real_detector_files():
    on_disk = doctor._detector_names_on_disk()
    assert "__init__" not in on_disk
    assert "autonomous_tx" in on_disk
    assert "dbms_utl_calls" in on_disk  # a real detector with no registered GAP-NNN
    assert len(on_disk) >= 29


def test_architecture_doc_parity_is_clean_on_the_real_repository_state():
    # Integration-style, same spirit as test_gap_registry.py's invariant
    # tests: this must hold against the actual docs/ARCHITECTURE.md/
    # detectors/ in this checkout, not a synthetic fixture -- that's the
    # whole point of the check.
    assert doctor.check_architecture_doc_parity() == []


def test_architecture_doc_parity_flags_a_detector_file_missing_from_the_doc(monkeypatch):
    monkeypatch.setattr(doctor, "_detector_names_on_disk", lambda: {"autonomous_tx", "brand_new_detector"})
    monkeypatch.setattr(doctor, "_detector_names_in_architecture_doc", lambda: {"autonomous_tx"})
    problems = doctor.check_architecture_doc_parity()
    assert len(problems) == 1
    assert "brand_new_detector.py" in problems[0]
    assert "не упомянут" in problems[0]


def test_architecture_doc_parity_flags_a_stale_entry_for_a_removed_detector(monkeypatch):
    monkeypatch.setattr(doctor, "_detector_names_on_disk", lambda: {"autonomous_tx"})
    monkeypatch.setattr(
        doctor, "_detector_names_in_architecture_doc", lambda: {"autonomous_tx", "long_removed_detector"}
    )
    problems = doctor.check_architecture_doc_parity()
    assert len(problems) == 1
    assert "long_removed_detector.py" in problems[0]
    assert "нет в ora2pg_gap_report/detectors/" in problems[0]


def test_gap_registry_row_regex_extracts_number_severity_and_versions_from_a_realistic_row():
    fragment = (
        "| ID | Конструкция | Детектор | Severity | Статус | ora2pg | PostgreSQL | Документ |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| GAP-001 | some construct | `autonomous_tx` | high | confirmed | 25.0 | 16 | [gap-001](gap-001.md) |\n"
        "| GAP-002 | fixed upstream one | `whatever` | high | fixed-upstream | 24.0 | 15 | [gap-002](gap-002.md) |\n"
    )
    matches = doctor._GAP_REGISTRY_ROW_RE.findall(fragment)
    # Only the 'confirmed' row is matched -- a fixed-upstream/wont-fix row
    # has no corresponding tracked version in gap_registry.py to compare
    # against, so it's deliberately not parsed as if it were confirmed.
    assert matches == [("001", "high", "25.0", "16")]


def test_gap_registry_row_regex_accepts_dotted_postgresql_versions():
    # A digits-only PostgreSQL column pattern would silently fail to
    # match a future dotted version ("16.4", or a pre-PG10 "9.6") --
    # the row would then be excluded from confirmed_rows entirely and
    # check_gap_registry_md_parity() would skip comparing it instead of
    # flagging a real mismatch, defeating the whole point of the check.
    fragment = "| GAP-001 | x | `autonomous_tx` | high | confirmed | 25.0 | 16.4 | [x](x.md) |\n"
    assert doctor._GAP_REGISTRY_ROW_RE.findall(fragment) == [("001", "high", "25.0", "16.4")]


def test_gap_registry_md_parity_is_clean_on_the_real_repository_state():
    # Integration-style, same spirit as the ARCHITECTURE.md parity test:
    # must hold against the actual docs/research/GAP_REGISTRY.md/
    # gap_registry.py in this checkout.
    assert doctor.check_gap_registry_md_parity() == []


def test_confirmed_gap_versions_in_text_ignores_non_confirmed_rows():
    fragment = (
        "| GAP-001 | some construct | `autonomous_tx` | high | confirmed | 25.0 | 16 | [gap-001](gap-001.md) |\n"
        "| GAP-002 | fixed upstream one | `whatever` | high | fixed-upstream | 24.0 | 15 | [gap-002](gap-002.md) |\n"
    )
    versions = doctor._confirmed_gap_versions_in_text(fragment)
    assert versions == {"001": ("high", "25.0", "16")}
    assert "002" not in versions


def test_gap_registry_md_parity_flags_a_version_mismatch(monkeypatch):
    monkeypatch.setattr(doctor, "GAPS", [gap_by_number("001")])
    monkeypatch.setattr(
        doctor,
        "_confirmed_gap_versions_in_text",
        lambda text: {"001": ("high", "99.9", "16")},
    )
    problems = doctor.check_gap_registry_md_parity()
    assert len(problems) == 1
    assert "GAP-001" in problems[0]
    assert "99.9" in problems[0]


def test_gap_registry_md_parity_flags_a_severity_mismatch(monkeypatch):
    monkeypatch.setattr(doctor, "GAPS", [gap_by_number("001")])
    monkeypatch.setattr(
        doctor,
        "_confirmed_gap_versions_in_text",
        lambda text: {"001": ("low", "25.0", "16")},
    )
    problems = doctor.check_gap_registry_md_parity()
    assert len(problems) == 1
    assert "GAP-001" in problems[0]
    assert "low" in problems[0]


def test_gap_registry_md_parity_skips_a_gap_with_no_matching_confirmed_row(monkeypatch):
    # A gap the table marks fixed-upstream/wont-fix instead of confirmed
    # has nothing in gap_registry.py to compare it against -- must not be
    # reported as drift.
    monkeypatch.setattr(doctor, "GAPS", [gap_by_number("001")])
    monkeypatch.setattr(doctor, "_confirmed_gap_versions_in_text", lambda text: {})
    assert doctor.check_gap_registry_md_parity() == []


def test_i18n_translations_parity_is_clean_on_the_real_repository_state():
    # Integration-style, same spirit as the other parity tests: must hold
    # against the real detectors/ and i18n.py in this checkout.
    assert doctor.check_i18n_translations_parity() == []


def test_i18n_translations_parity_flags_a_detector_message_with_no_english_translation(monkeypatch):
    monkeypatch.setattr(
        doctor,
        "_detector_message_constants",
        lambda: [("brand_new_detector", "_MESSAGE", "a message with no translation")],
    )
    problems = doctor.check_i18n_translations_parity()
    assert len(problems) == 1
    assert "brand_new_detector._MESSAGE" in problems[0]
    assert "no English translation" in problems[0]


def test_i18n_translations_parity_flags_a_missing_remediation_hint(monkeypatch):
    monkeypatch.setattr(doctor, "_detector_message_constants", lambda: [])
    monkeypatch.setattr(doctor, "_REMEDIATION_HINT", {"brand_new_detector": "some hint"})
    problems = doctor.check_i18n_translations_parity()
    assert len(problems) == 1
    assert "REMEDIATION_HINT_EN is missing an entry for 'brand_new_detector'" in problems[0]


def test_verification_mode_parity_is_clean_on_the_real_repository_state():
    assert doctor.check_verification_mode_parity() == []


def test_verification_mode_parity_flags_a_detector_missing_from_verification_mode(monkeypatch):
    monkeypatch.setattr(doctor, "_detector_names_on_disk", lambda: {"autonomous_tx", "brand_new_detector"})
    monkeypatch.setattr(doctor, "VERIFICATION_MODE", {"autonomous_tx": "not_verifiable"})
    problems = doctor.check_verification_mode_parity()
    assert len(problems) == 1
    assert "brand_new_detector" in problems[0]
    assert "не имеет записи" in problems[0]


def test_verification_mode_parity_flags_a_stale_entry_for_a_removed_detector(monkeypatch):
    monkeypatch.setattr(doctor, "_detector_names_on_disk", lambda: {"autonomous_tx"})
    monkeypatch.setattr(
        doctor, "VERIFICATION_MODE", {"autonomous_tx": "not_verifiable", "long_removed": "verbatim"}
    )
    problems = doctor.check_verification_mode_parity()
    assert len(problems) == 1
    assert "long_removed" in problems[0]
    assert "нет в ora2pg_gap_report/detectors/" in problems[0]


def test_scan_loop_registration_parity_is_clean_on_the_real_repository_state():
    assert doctor.check_scan_loop_registration_parity() == []


def test_scan_loop_registration_parity_flags_a_detector_missing_from_detectors_tuple(monkeypatch):
    # A module that exists on disk, is fully registered everywhere else,
    # and has passing tests, but was never added to cli.py's _DETECTORS --
    # it would silently never actually run during a real scan_source()
    # call, and nothing else in this project's test suite catches that in
    # general (see check_scan_loop_registration_parity()'s own docstring).
    monkeypatch.setattr(doctor, "_detector_names_on_disk", lambda: {"autonomous_tx", "brand_new_detector"})
    monkeypatch.setattr(doctor, "detector_names", lambda: ("autonomous_tx",))
    problems = doctor.check_scan_loop_registration_parity()
    assert len(problems) == 1
    assert "brand_new_detector" in problems[0]
    assert "не добавлен в _DETECTORS" in problems[0]


def test_scan_loop_registration_parity_flags_a_stale_entry_for_a_removed_detector(monkeypatch):
    monkeypatch.setattr(doctor, "_detector_names_on_disk", lambda: {"autonomous_tx"})
    monkeypatch.setattr(doctor, "detector_names", lambda: ("autonomous_tx", "long_removed"))
    problems = doctor.check_scan_loop_registration_parity()
    assert len(problems) == 1
    assert "long_removed" in problems[0]
    assert "нет в" in problems[0]


def test_scan_loop_registration_parity_does_not_require_connect_by_in_the_scan_loop(monkeypatch):
    # connect_by is deliberately opt-in via --check-connect-by, not part
    # of the main scan loop -- on disk but absent from _DETECTORS is its
    # normal, expected state, not something to flag.
    monkeypatch.setattr(doctor, "_detector_names_on_disk", lambda: {"autonomous_tx", "connect_by"})
    monkeypatch.setattr(doctor, "detector_names", lambda: ("autonomous_tx",))
    assert doctor.check_scan_loop_registration_parity() == []


def test_failure_stage_values_is_clean_on_the_real_repository_state():
    # Full coverage is required now (rollout is complete), except for the
    # two gaps in FAILURE_STAGE_EXEMPT_DETECTORS.
    assert doctor.check_failure_stage_values() == []


def test_failure_stage_values_flags_an_unknown_stage(monkeypatch):
    fake_gap = GapEntry("999", "brand_new_detector", "brand-new", (), severity="high", failure_stage="mid_flight")
    monkeypatch.setattr(doctor, "GAPS", (fake_gap,))
    problems = doctor.check_failure_stage_values()
    assert len(problems) == 1
    assert "GAP-999" in problems[0]
    assert "mid_flight" in problems[0]


def test_failure_stage_values_flags_a_new_gap_left_unset(monkeypatch):
    # A gap not in FAILURE_STAGE_EXEMPT_DETECTORS must have a
    # failure_stage -- unset is only allowed for the two documented
    # exceptions, not a silent default for every new gap going forward.
    fake_gap = GapEntry("999", "brand_new_detector", "brand-new", (), severity="high")  # failure_stage defaults to None
    monkeypatch.setattr(doctor, "GAPS", (fake_gap,))
    problems = doctor.check_failure_stage_values()
    assert len(problems) == 1
    assert "GAP-999" in problems[0]
    assert "не задан" in problems[0]


def test_failure_stage_values_allows_unset_for_exempt_detectors(monkeypatch):
    fake_gap = GapEntry("001", "autonomous_tx", "autonomous-transaction", (), severity="high")
    monkeypatch.setattr(doctor, "GAPS", (fake_gap,))
    assert doctor.check_failure_stage_values() == []


def test_gap_severity_matches_detector_source_is_clean_on_the_real_repository_state():
    # Integration-style, same spirit as the other parity tests: must hold
    # against the real gap_registry.py and detectors/ in this checkout --
    # this is the check that would have caught the exact class of drift
    # this field is meant to prevent (registry claims one severity, a
    # later edit to the detector's own code emits another).
    assert doctor.check_gap_severity_matches_detector_source() == []


def test_gap_severity_matches_detector_source_flags_an_invalid_value(monkeypatch):
    fake_gap = dataclasses.replace(gap_by_number("028"), severity="critical")
    monkeypatch.setattr(doctor, "GAPS", (fake_gap,))
    problems = doctor.check_gap_severity_matches_detector_source()
    assert len(problems) == 1
    assert "GAP-028" in problems[0]
    assert "critical" in problems[0]


def test_gap_severity_matches_detector_source_flags_a_mismatch_against_the_real_detector(monkeypatch):
    # identity_column's own source really does use severity="high" --
    # claiming "medium" in the registry must be caught against the real
    # file, not a mock.
    fake_gap = dataclasses.replace(gap_by_number("028"), severity="medium")
    monkeypatch.setattr(doctor, "GAPS", (fake_gap,))
    problems = doctor.check_gap_severity_matches_detector_source()
    assert len(problems) == 1
    assert "GAP-028" in problems[0]
    assert "medium" in problems[0]
    assert "high" in problems[0]


def test_gap_severity_matches_detector_source_flags_multiple_severities_in_one_file(monkeypatch, tmp_path):
    detectors_dir = tmp_path / "ora2pg_gap_report" / "detectors"
    detectors_dir.mkdir(parents=True)
    (detectors_dir / "fake_detector.py").write_text(
        'severity="high"\nseverity="medium"\n', encoding="utf-8"
    )
    monkeypatch.setattr(doctor, "REPO_ROOT", tmp_path)
    fake_gap = GapEntry("999", "fake_detector", "fake-detector", (), severity="high")
    monkeypatch.setattr(doctor, "GAPS", (fake_gap,))
    problems = doctor.check_gap_severity_matches_detector_source()
    assert len(problems) == 1
    assert "GAP-999" in problems[0]
    assert "несколько" in problems[0]


def test_gap_severity_matches_detector_source_flags_no_severity_literal_found(monkeypatch, tmp_path):
    detectors_dir = tmp_path / "ora2pg_gap_report" / "detectors"
    detectors_dir.mkdir(parents=True)
    (detectors_dir / "fake_detector.py").write_text("# no severity literal here\n", encoding="utf-8")
    monkeypatch.setattr(doctor, "REPO_ROOT", tmp_path)
    fake_gap = GapEntry("999", "fake_detector", "fake-detector", (), severity="high")
    monkeypatch.setattr(doctor, "GAPS", (fake_gap,))
    problems = doctor.check_gap_severity_matches_detector_source()
    assert len(problems) == 1
    assert "GAP-999" in problems[0]


def test_gap_severity_matches_detector_source_skips_a_missing_detector_file(monkeypatch, tmp_path):
    # A missing detector file is already reported by check_gap() -- this
    # check must not pile on a second, duplicate complaint about the same
    # underlying problem.
    monkeypatch.setattr(doctor, "REPO_ROOT", tmp_path)
    fake_gap = GapEntry("999", "brand_new_detector", "brand-new", (), severity="high")
    monkeypatch.setattr(doctor, "GAPS", (fake_gap,))
    assert doctor.check_gap_severity_matches_detector_source() == []
