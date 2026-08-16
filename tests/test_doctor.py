"""Tests for scripts/doctor.py's README <-> detectors-on-disk parity
check -- the specific class of drift this catches (README.md's
"Архитектура" file tree silently falling behind ora2pg_gap_report/
detectors/) was found and fixed by hand once already; this makes it a
rerunnable check instead of something that has to be rediscovered by
rereading the whole README."""

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "doctor.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("doctor", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


doctor = _load_module()


def test_detector_regex_extracts_names_from_a_realistic_tree_fragment():
    fragment = (
        "├── detectors/\n"
        "│   ├── autonomous_tx.py        # PRAGMA AUTONOMOUS_TRANSACTION\n"
        "│   ├── with_function.py         # WITH FUNCTION / WITH PROCEDURE\n"
        "│   └── identity_column.py       # last entry, uses the closing branch\n"
        "├── ora2pg_wrapper.py            # not a detector -- sibling of detectors/\n"
        "├── cli.py                      # not a detector either\n"
    )
    names = set(doctor._README_DETECTOR_RE.findall(fragment))
    assert names == {"autonomous_tx", "with_function", "identity_column"}
    assert "ora2pg_wrapper" not in names
    assert "cli" not in names


def test_detector_names_on_disk_matches_real_detector_files():
    on_disk = doctor._detector_names_on_disk()
    assert "__init__" not in on_disk
    assert "autonomous_tx" in on_disk
    assert "dbms_utl_calls" in on_disk  # a real detector with no registered GAP-NNN
    assert len(on_disk) >= 28


def test_readme_parity_is_clean_on_the_real_repository_state():
    # Integration-style, same spirit as test_gap_registry.py's invariant
    # tests: this must hold against the actual README.md/detectors/ in
    # this checkout, not a synthetic fixture -- that's the whole point of
    # the check.
    assert doctor.check_readme_parity() == []


def test_readme_parity_flags_a_detector_file_missing_from_the_readme(monkeypatch):
    monkeypatch.setattr(doctor, "_detector_names_on_disk", lambda: {"autonomous_tx", "brand_new_detector"})
    monkeypatch.setattr(doctor, "_detector_names_in_readme", lambda: {"autonomous_tx"})
    problems = doctor.check_readme_parity()
    assert len(problems) == 1
    assert "brand_new_detector.py" in problems[0]
    assert "не упомянут" in problems[0]


def test_readme_parity_flags_a_stale_readme_entry_for_a_removed_detector(monkeypatch):
    monkeypatch.setattr(doctor, "_detector_names_on_disk", lambda: {"autonomous_tx"})
    monkeypatch.setattr(doctor, "_detector_names_in_readme", lambda: {"autonomous_tx", "long_removed_detector"})
    problems = doctor.check_readme_parity()
    assert len(problems) == 1
    assert "long_removed_detector.py" in problems[0]
    assert "нет в ora2pg_gap_report/detectors/" in problems[0]
