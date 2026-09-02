"""Tests for ora2pg_gap_report/i18n.py -- language resolution order and
persistence, and that every detector's message/hint has an English
counterpart (the integration-style check mirrors scripts/doctor.py's own
check_i18n_translations_parity(), same spirit as test_gap_registry.py's
invariant tests: it must hold against the real detectors/i18n.py in this
checkout, not a synthetic fixture)."""

import glob
import importlib
from pathlib import Path

import pytest

from ora2pg_gap_report import i18n
from ora2pg_gap_report.terminal_report import _REMEDIATION_HINT


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    """Every test gets its own, empty config directory -- otherwise a
    --set-lang choice saved by a real run on the machine executing the
    tests would leak into resolve_language()'s "saved" branch and make
    these tests order-dependent on developer machine state."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("ORA2PG_GAP_REPORT_LANG", raising=False)


def test_get_saved_language_is_none_when_nothing_was_ever_saved():
    assert i18n.get_saved_language() is None


def test_save_and_get_language_round_trips():
    i18n.save_language("en")
    assert i18n.get_saved_language() == "en"


def test_get_saved_language_ignores_a_corrupted_or_unrecognized_value(tmp_path):
    config_file = tmp_path / "ora2pg-gap-report" / "language"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("not-a-real-language", encoding="utf-8")
    assert i18n.get_saved_language() is None


def test_resolve_language_prefers_explicit_over_everything_else(monkeypatch):
    i18n.save_language("en")
    monkeypatch.setenv("ORA2PG_GAP_REPORT_LANG", "en")
    assert i18n.resolve_language("ru", interactive=False) == "ru"


def test_resolve_language_prefers_env_var_over_saved_choice(monkeypatch):
    i18n.save_language("ru")
    monkeypatch.setenv("ORA2PG_GAP_REPORT_LANG", "en")
    assert i18n.resolve_language(None, interactive=False) == "en"


def test_resolve_language_falls_back_to_saved_choice():
    i18n.save_language("en")
    assert i18n.resolve_language(None, interactive=False) == "en"


def test_resolve_language_defaults_to_russian_when_nothing_is_configured():
    # Non-interactive (the pytest/CI case) and nothing set anywhere --
    # must stay "ru", unchanged from before --lang existed, so every
    # existing script/CI config parsing this tool's Russian output keeps
    # working without modification.
    assert i18n.resolve_language(None, interactive=False) == "ru"


def test_resolve_language_does_not_prompt_when_not_interactive(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("prompt_language_interactively() must not be called")

    monkeypatch.setattr(i18n, "prompt_language_interactively", _boom)
    assert i18n.resolve_language(None, interactive=False) == "ru"


def test_resolve_language_prompts_and_saves_when_interactive_and_unconfigured(monkeypatch):
    monkeypatch.setattr(i18n, "prompt_language_interactively", lambda *a, **k: "en")
    assert i18n.resolve_language(None, interactive=True) == "en"
    # The picker's result is remembered -- a second run shouldn't prompt again.
    assert i18n.get_saved_language() == "en"


def test_t_falls_back_to_russian_for_a_language_with_no_english_translation():
    # Every _UI entry in this module has both "ru" and "en" today, but t()'s
    # own fallback (entry.get(lang, entry["ru"])) is exercised here directly
    # rather than assumed, in case that ever stops being true for one key.
    assert i18n.t("ru", "no_findings") == "Проблемных конструкций не найдено."


def test_t_formats_kwargs_into_the_template():
    assert i18n.t("en", "objects_scanned_inline", n=7) == "\nObjects scanned: 7"


def test_t_raises_for_an_unregistered_key():
    with pytest.raises(KeyError):
        i18n.t("ru", "this_key_does_not_exist")


def _detector_message_constants():
    items = []
    for f in sorted(glob.glob("ora2pg_gap_report/detectors/*.py")):
        # Path(f).stem, not f.split("/"): glob returns the platform's own
        # separator, so splitting on "/" leaves "detectors\foo" as the
        # "module name" on Windows and import_module then fails.
        name = Path(f).stem
        if name == "__init__":
            continue
        module = importlib.import_module(f"ora2pg_gap_report.detectors.{name}")
        for attr in vars(module):
            if attr.isupper() and "MESSAGE" in attr:
                items.append((name, attr, getattr(module, attr)))
    return items


def test_every_detector_message_constant_has_an_english_translation():
    missing = [
        f"{name}.{attr}"
        for name, attr, message in _detector_message_constants()
        if message not in i18n.EXPLANATION_EN
    ]
    assert missing == []


def test_every_remediation_hint_has_an_english_counterpart():
    missing = sorted(set(_REMEDIATION_HINT) - set(i18n.REMEDIATION_HINT_EN))
    assert missing == []


def test_translate_message_is_a_noop_for_russian():
    assert i18n.translate_message("some Russian text", "ru") == "some Russian text"


def test_translate_message_swaps_a_known_message_for_english():
    name, attr, ru_message = _detector_message_constants()[0]
    translated = i18n.translate_message(ru_message, "en")
    assert translated == i18n.EXPLANATION_EN[ru_message]
    assert translated != ru_message


def test_translate_message_falls_back_to_the_original_for_an_unknown_message():
    assert i18n.translate_message("not a registered message", "en") == "not a registered message"
