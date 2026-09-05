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
        "| ID | Конструкция | Детектор | Severity | Статус | ora2pg | PostgreSQL "
        "| Проверено | Документ |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        "| GAP-001 | some construct | `autonomous_tx` | high | confirmed | 25.0 | 16 "
        "| 2026-08-14 | [gap-001](gap-001.md) |\n"
        "| GAP-002 | fixed upstream one | `whatever` | high | fixed-upstream | 24.0 | 15 "
        "| — | [gap-002](gap-002.md) |\n"
    )
    matches = doctor._GAP_REGISTRY_ROW_RE.findall(fragment)
    # Only the 'confirmed' row is matched -- a fixed-upstream/wont-fix row
    # has no corresponding tracked version in gap_registry.py to compare
    # against, so it's deliberately not parsed as if it were confirmed.
    assert matches == [("001", "high", "25.0", "16", "2026-08-14")]


def test_gap_registry_row_regex_accepts_dotted_postgresql_versions():
    # A digits-only PostgreSQL column pattern would silently fail to
    # match a future dotted version ("16.4", or a pre-PG10 "9.6") --
    # the row would then be excluded from confirmed_rows entirely and
    # check_gap_registry_md_parity() would skip comparing it instead of
    # flagging a real mismatch, defeating the whole point of the check.
    fragment = (
        "| GAP-001 | x | `autonomous_tx` | high | confirmed | 25.0 | 16.4 "
        "| 2026-08-14 | [x](x.md) |\n"
    )
    assert doctor._GAP_REGISTRY_ROW_RE.findall(fragment) == [
        ("001", "high", "25.0", "16.4", "2026-08-14")
    ]


def test_gap_registry_md_parity_is_clean_on_the_real_repository_state():
    # Integration-style, same spirit as the ARCHITECTURE.md parity test:
    # must hold against the actual docs/research/GAP_REGISTRY.md/
    # gap_registry.py in this checkout.
    assert doctor.check_gap_registry_md_parity() == []


def test_confirmed_gap_versions_in_text_ignores_non_confirmed_rows():
    fragment = (
        "| GAP-001 | some construct | `autonomous_tx` | high | confirmed | 25.0 | 16 "
        "| 2026-08-14 | [gap-001](gap-001.md) |\n"
        "| GAP-002 | fixed upstream one | `whatever` | high | fixed-upstream | 24.0 | 15 "
        "| — | [gap-002](gap-002.md) |\n"
    )
    versions = doctor._confirmed_gap_versions_in_text(fragment)
    assert versions == {"001": ("high", "25.0", "16", "2026-08-14")}
    assert "002" not in versions


def test_gap_registry_md_parity_flags_a_version_mismatch(monkeypatch):
    monkeypatch.setattr(doctor, "GAPS", [gap_by_number("001")])
    monkeypatch.setattr(
        doctor,
        "_confirmed_gap_versions_in_text",
        lambda text: {"001": ("high", "99.9", "16", gap_by_number("001").last_verified)},
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
        lambda text: {"001": ("low", "25.0", "16", gap_by_number("001").last_verified)},
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


def test_i18n_translations_parity_flags_a_detector_wired_to_an_unknown_message_id(monkeypatch):
    monkeypatch.setattr(
        doctor, "_detector_message_ids", lambda: {"brand_new_detector": "no_such_id"}
    )
    problems = doctor.check_i18n_translations_parity()
    assert len(problems) == 1
    assert "brand_new_detector" in problems[0]
    assert "no_such_id" in problems[0]


def test_i18n_translations_parity_flags_a_blank_translation(monkeypatch):
    # The remaining silent failure once ids replaced text as the key: the
    # id resolves, so nothing raises, and the user just gets an empty
    # explanation.
    monkeypatch.setattr(doctor, "_detector_message_ids", lambda: {"d": "d"})
    monkeypatch.setattr(
        doctor.messages, "MESSAGES", {"d": doctor.messages.Message(ru="есть текст", en="   ")}
    )
    monkeypatch.setattr(doctor, "_detector_names_on_disk", lambda: set())
    monkeypatch.setattr(doctor.messages, "REMEDIATION_HINTS", {})
    problems = doctor.check_i18n_translations_parity()
    assert len(problems) == 1
    assert "MESSAGES['d'].en is empty" in problems[0]


def test_i18n_translations_parity_flags_a_missing_remediation_hint(monkeypatch):
    monkeypatch.setattr(doctor, "_detector_message_ids", lambda: {})
    monkeypatch.setattr(doctor, "_detector_names_on_disk", lambda: {"brand_new_detector"})
    monkeypatch.setattr(doctor.messages, "REMEDIATION_HINTS", {})
    problems = doctor.check_i18n_translations_parity()
    assert len(problems) == 1
    assert "REMEDIATION_HINTS has no entry for 'brand_new_detector'" in problems[0]


def test_i18n_translations_parity_flags_a_hint_naming_no_detector(monkeypatch):
    # The other direction: a hint left behind after its detector was
    # renamed or removed still reads as live advice.
    monkeypatch.setattr(doctor, "_detector_message_ids", lambda: {})
    monkeypatch.setattr(doctor, "_detector_names_on_disk", lambda: set())
    monkeypatch.setattr(
        doctor.messages, "REMEDIATION_HINTS",
        {"gone": doctor.messages.Message(ru="совет", en="hint")},
    )
    problems = doctor.check_i18n_translations_parity()
    assert len(problems) == 1
    assert "REMEDIATION_HINTS['gone'] names no detector on disk" in problems[0]


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
    # and has passing tests, but was never added to any dialect's own
    # detector tuple in core.py -- it would silently never actually run
    # during a real scan_source() call, and nothing else in this
    # project's test suite catches that in general (see
    # check_scan_loop_registration_parity()'s own docstring).
    monkeypatch.setattr(doctor, "_detector_names_on_disk", lambda: {"autonomous_tx", "brand_new_detector"})
    monkeypatch.setattr(doctor, "detector_names", lambda: ("autonomous_tx",))
    problems = doctor.check_scan_loop_registration_parity()
    assert len(problems) == 1
    assert "brand_new_detector" in problems[0]
    assert "не добавлен ни в один диалект" in problems[0]


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
    fake_gap = GapEntry("999", "brand_new_detector", "brand-new", (), severity="high", failure_stage="mid_flight", last_verified="2026-01-01")
    monkeypatch.setattr(doctor, "GAPS", (fake_gap,))
    problems = doctor.check_failure_stage_values()
    assert len(problems) == 1
    assert "GAP-999" in problems[0]
    assert "mid_flight" in problems[0]


def test_failure_stage_values_flags_a_new_gap_left_unset(monkeypatch):
    # A gap not in FAILURE_STAGE_EXEMPT_DETECTORS must have a
    # failure_stage -- unset is only allowed for the two documented
    # exceptions, not a silent default for every new gap going forward.
    fake_gap = GapEntry("999", "brand_new_detector", "brand-new", (), severity="high", last_verified="2026-01-01")  # failure_stage defaults to None
    monkeypatch.setattr(doctor, "GAPS", (fake_gap,))
    problems = doctor.check_failure_stage_values()
    assert len(problems) == 1
    assert "GAP-999" in problems[0]
    assert "не задан" in problems[0]


def test_failure_stage_values_allows_unset_for_exempt_detectors(monkeypatch):
    fake_gap = GapEntry("001", "autonomous_tx", "autonomous-transaction", (), severity="high", last_verified="2026-01-01")
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
    fake_gap = GapEntry("999", "fake_detector", "fake-detector", (), severity="high", last_verified="2026-01-01")
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
    fake_gap = GapEntry("999", "fake_detector", "fake-detector", (), severity="high", last_verified="2026-01-01")
    monkeypatch.setattr(doctor, "GAPS", (fake_gap,))
    problems = doctor.check_gap_severity_matches_detector_source()
    assert len(problems) == 1
    assert "GAP-999" in problems[0]


def test_gap_severity_matches_detector_source_skips_a_missing_detector_file(monkeypatch, tmp_path):
    # A missing detector file is already reported by check_gap() -- this
    # check must not pile on a second, duplicate complaint about the same
    # underlying problem.
    monkeypatch.setattr(doctor, "REPO_ROOT", tmp_path)
    fake_gap = GapEntry("999", "brand_new_detector", "brand-new", (), severity="high", last_verified="2026-01-01")
    monkeypatch.setattr(doctor, "GAPS", (fake_gap,))
    assert doctor.check_gap_severity_matches_detector_source() == []


def test_translations_are_not_glued_is_clean_on_the_real_repository_state():
    # Integration-style, same spirit as the other parity tests. This one
    # exists because the bug it catches actually shipped: a batch of
    # translations was generated with a line-wrapper that stripped the
    # separating spaces, producing "anobject type" and similar. Every
    # other check passed on that state -- the translations were present
    # and the module imported fine.
    assert doctor.check_translations_are_not_glued() == []


def test_translations_are_not_glued_flags_a_glued_word(monkeypatch):
    monkeypatch.setattr(
        doctor.messages,
        "MESSAGES",
        {"some_detector": doctor.messages.Message(
            ru="какое-то русское сообщение",
            en="an Oracle table where anobjecttypeinstance lives",
        )},
    )
    monkeypatch.setattr(doctor.messages, "REMEDIATION_HINTS", {})
    problems = doctor.check_translations_are_not_glued()
    assert len(problems) == 1
    assert "anobjecttypeinstance" in problems[0]
    assert "MESSAGES.en" in problems[0]


def test_translations_are_not_glued_also_checks_remediation_hints(monkeypatch):
    monkeypatch.setattr(doctor.messages, "MESSAGES", {})
    monkeypatch.setattr(
        doctor.messages, "REMEDIATION_HINTS",
        {"some_detector": doctor.messages.Message(
            ru="нормальный совет", en="rewriteusingwindowfunctions instead"
        )},
    )
    problems = doctor.check_translations_are_not_glued()
    assert len(problems) == 1
    assert "REMEDIATION_HINTS.en" in problems[0]


def test_translations_are_not_glued_checks_the_russian_side_too(monkeypatch):
    # Both languages go through the same line-wrapping, so both can lose a
    # separator on the seam between adjacent string literals.
    monkeypatch.setattr(
        doctor.messages,
        "MESSAGES",
        {"some_detector": doctor.messages.Message(
            ru="таблица где живёт anobjecttypeinstance", en="fine text here"
        )},
    )
    monkeypatch.setattr(doctor.messages, "REMEDIATION_HINTS", {})
    problems = doctor.check_translations_are_not_glued()
    assert len(problems) == 1
    assert "MESSAGES.ru" in problems[0]


def test_translations_are_not_glued_allows_ordinary_text(monkeypatch):
    monkeypatch.setattr(
        doctor.messages,
        "MESSAGES",
        {"some_detector": doctor.messages.Message(
            ru="обычный текст без склеек",
            en="an Oracle object table: every row is an instance of an object type",
        )},
    )
    monkeypatch.setattr(doctor.messages, "REMEDIATION_HINTS", {})
    assert doctor.check_translations_are_not_glued() == []


def test_last_verified_dates_are_clean_on_the_real_repository_state():
    assert doctor.check_last_verified_dates() == []


def test_last_verified_flags_a_malformed_date(monkeypatch):
    gap = GapEntry("999", "d", "d", (), severity="high", last_verified="14.08.2026")
    monkeypatch.setattr(doctor, "GAPS", (gap,))
    problems = doctor.check_last_verified_dates()
    assert len(problems) == 1
    assert "is not an ISO yyyy-mm-dd date" in problems[0]


def test_last_verified_flags_a_date_in_the_future(monkeypatch):
    # A mistyped year turns the evidence line into decoration.
    gap = GapEntry("999", "d", "d", (), severity="high", last_verified="2999-01-01")
    monkeypatch.setattr(doctor, "GAPS", (gap,))
    problems = doctor.check_last_verified_dates()
    assert len(problems) == 1
    assert "is in the future" in problems[0]


def test_gap_registry_md_parity_flags_a_drifted_verification_date(monkeypatch, tmp_path):
    # The column was added after the table already had ora2pg/PostgreSQL
    # ones, and the row regex stopped before it -- so it parsed fine while
    # guarding nothing. This is the test that the column is actually
    # compared.
    gap = GapEntry(
        "001", "autonomous_tx", "autonomous-transaction", (),
        severity="high", last_verified="2026-08-14",
    )
    monkeypatch.setattr(doctor, "GAPS", (gap,))
    rows = doctor._confirmed_gap_versions_in_text(
        "| GAP-001 | x | `autonomous_tx` | high | confirmed | 25.0 | 16 | 2020-01-01 | [d](d.md) |\n"
    )
    assert rows["001"] == ("high", "25.0", "16", "2020-01-01")

    monkeypatch.setattr(doctor, "_confirmed_gap_versions_in_text", lambda _text: rows)
    problems = doctor.check_gap_registry_md_parity()
    assert len(problems) == 1
    assert "дату проверки 2020-01-01" in problems[0]
