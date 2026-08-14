from pathlib import Path

from ora2pg_gap_report.detectors.autonomous_tx import find_autonomous_transactions

SAMPLES = Path(__file__).resolve().parents[1] / "docs" / "research" / "samples"

# Confirmed by manual inspection of logger.pkb (OraOpenSource/Logger) —
# see docs/research/step0-show-report-baseline.md.
EXPECTED_OBJECTS = {
    "LOGGER.SAVE_GLOBAL_CONTEXT",
    "LOGGER.NULL_GLOBAL_CONTEXTS",
    "LOGGER.LOG_APEX_ITEMS",
    "LOGGER.PURGE",
    "LOGGER.PURGE_ALL",
    "LOGGER.SET_LEVEL",
    "LOGGER.UNSET_CLIENT_LEVEL",
    "LOGGER.INS_LOGGER_LOGS",
}


def test_detects_all_known_occurrences_in_logger_pkb():
    source = (SAMPLES / "logger.pkb").read_text()
    findings = find_autonomous_transactions(source)

    assert {f.object_name for f in findings} == EXPECTED_OBJECTS
    assert len(findings) == len(EXPECTED_OBJECTS)


def test_finding_shape():
    source = (SAMPLES / "logger.pkb").read_text()
    findings = find_autonomous_transactions(source)
    finding = next(f for f in findings if f.object_name == "LOGGER.PURGE_ALL")

    assert finding.detector == "autonomous_tx"
    assert finding.severity == "high"
    assert finding.snippet.lower() == "pragma autonomous_transaction;"
    assert finding.line > 0
    assert "dblink" in finding.message


def test_no_false_positives_on_packages_without_the_pragma():
    for filename in ("sql_util_pkg.pkb", "file_util_pkg.pkb"):
        source = (SAMPLES / filename).read_text()
        assert find_autonomous_transactions(source) == []


def test_ignores_pragma_mentioned_only_in_a_comment():
    source = """
    create or replace package body demo as
      -- note: pragma autonomous_transaction; is NOT actually used here
      procedure noop is
      begin
        null;
      end noop;
    end demo;
    /
    """
    assert find_autonomous_transactions(source) == []


def test_does_not_confuse_pragma_in_one_routine_for_another():
    source = """
    create or replace package body demo as
      procedure with_pragma is
        pragma autonomous_transaction;
      begin
        commit;
      end with_pragma;

      procedure without_pragma is
      begin
        null;
      end without_pragma;
    end demo;
    /
    """
    findings = find_autonomous_transactions(source)
    assert {f.object_name for f in findings} == {"DEMO.WITH_PRAGMA"}
