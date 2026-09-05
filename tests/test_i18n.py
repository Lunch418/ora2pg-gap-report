"""Tests for ora2pg_gap_report/i18n.py -- language resolution order and
persistence, and that every detector's message/hint has an English
counterpart (the integration-style check mirrors scripts/doctor.py's own
check_i18n_translations_parity(), same spirit as test_gap_registry.py's
invariant tests: it must hold against the real detectors/i18n.py in this
checkout, not a synthetic fixture)."""


import pytest

from ora2pg_gap_report import i18n, messages


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


def test_every_detector_message_id_resolves_in_both_languages():
    # The replacement for the old "every Russian message string has an
    # EXPLANATION_EN entry" check. The failure it guards is different now
    # -- an unknown id raises rather than silently falling back to
    # Russian -- but a blank translation would still ship quietly.
    for message_id, message in messages.MESSAGES.items():
        assert message.ru.strip(), f"{message_id}: empty Russian text"
        assert message.en.strip(), f"{message_id}: empty English text"
        assert messages.text(message_id, "en") == message.en
        assert messages.text(message_id, "ru") == message.ru


def test_an_unknown_message_id_raises_rather_than_rendering_nothing():
    with pytest.raises(KeyError):
        messages.text("no_such_message_id")


def test_an_unrecognized_language_falls_back_to_russian():
    any_id = next(iter(messages.MESSAGES))
    assert messages.text(any_id, "de") == messages.MESSAGES[any_id].ru


def test_every_remediation_hint_carries_both_languages():
    # The pair used to live in two files -- ru in terminal_report.py, en in
    # i18n.py -- so "has an English counterpart" was a real question. Now
    # one Message holds both and the question is whether either half is
    # blank.
    blank = sorted(
        name for name, hint in messages.REMEDIATION_HINTS.items()
        if not hint.ru.strip() or not hint.en.strip()
    )
    assert blank == []


def test_remediation_hint_falls_back_to_russian_for_an_unknown_language():
    name = next(iter(messages.REMEDIATION_HINTS))
    assert messages.remediation_hint(name, "de") == messages.REMEDIATION_HINTS[name].ru


def test_remediation_hint_is_none_for_a_detector_without_one():
    # Not an error, unlike a missing message: the report falls back to a
    # generic line.
    assert messages.remediation_hint("no_such_detector") is None
