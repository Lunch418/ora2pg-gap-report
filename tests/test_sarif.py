"""SARIF output tests. The vendored schema at
tests/fixtures/sarif-2.1.0.schema.json is the official OASIS SARIF 2.1.0
JSON Schema (fetched once from https://json.schemastore.org/sarif-2.1.0.json
and committed here so validation doesn't depend on network access during
test runs) -- every test below validates real to_sarif() output against
it directly, not just against hand-written expectations about its shape."""

import json
from pathlib import Path

import jsonschema
import pytest

from ora2pg_gap_report.cli import scan_source
from ora2pg_gap_report.models import Finding
from ora2pg_gap_report.report_generator import to_sarif

SAMPLES = Path(__file__).resolve().parents[1] / "docs" / "research" / "samples"
_SCHEMA_PATH = Path(__file__).resolve().parent / "fixtures" / "sarif-2.1.0.schema.json"


@pytest.fixture(scope="module")
def sarif_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text())


def test_empty_findings_produce_valid_sarif(sarif_schema):
    doc = json.loads(to_sarif([]))
    jsonschema.validate(doc, sarif_schema)
    assert doc["runs"][0]["results"] == []
    assert doc["runs"][0]["tool"]["driver"]["rules"] == []


def test_real_scan_produces_valid_sarif(sarif_schema):
    findings = scan_source((SAMPLES / "logger.pkb").read_text())
    assert findings, "expected at least one finding to make this a meaningful check"
    doc = json.loads(to_sarif(findings, tool_version="1.2.3"))
    jsonschema.validate(doc, sarif_schema)

    driver = doc["runs"][0]["tool"]["driver"]
    assert driver["name"] == "ora2pg-gap-report"
    assert driver["version"] == "1.2.3"
    assert len(doc["runs"][0]["results"]) == len(findings)
    # One rule per distinct (detector, message) pair present, not one per
    # finding and not one per detector -- a detector can have more than
    # one static message (see test_multiple_messages_from_one_detector_
    # gets_separate_rules), so grouping by detector alone would be wrong.
    assert len(driver["rules"]) == len({(f.detector, f.message) for f in findings})


def test_line_zero_sentinel_produces_valid_sarif_without_a_region(sarif_schema):
    # line=0 is this project's "not a line in this file" sentinel (see
    # cli.py's _connect_by_check()) -- SARIF regions are 1-based, so
    # emitting startLine=0 would be an invalid document, not just wrong.
    finding = Finding(
        detector="connect_by",
        severity="high",
        object_name="PKG.PROC",
        line=0,
        snippet="c.level",
        message="msg",
        source_file="generated_output.sql",
    )
    doc = json.loads(to_sarif([finding]))
    jsonschema.validate(doc, sarif_schema)
    location = doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
    assert "region" not in location
    assert location["artifactLocation"]["uri"] == "generated_output.sql"


def test_severity_maps_to_the_expected_sarif_level():
    findings = [
        Finding(detector="a", severity="high", object_name="X", line=1, snippet="s", message="m"),
        Finding(detector="b", severity="medium", object_name="X", line=1, snippet="s", message="m"),
        Finding(detector="c", severity="low", object_name="X", line=1, snippet="s", message="m"),
    ]
    doc = json.loads(to_sarif(findings))
    results_by_detector = {f.detector: r for f, r in zip(findings, doc["runs"][0]["results"])}
    assert results_by_detector["a"]["level"] == "error"
    assert results_by_detector["b"]["level"] == "warning"
    assert results_by_detector["c"]["level"] == "note"


def test_rule_help_uri_points_at_the_gap_research_doc_when_one_exists():
    finding = Finding(
        detector="read_only_table",
        severity="high",
        object_name="AUDIT_LOG",
        line=4,
        snippet="READ ONLY",
        message="msg",
    )
    doc = json.loads(to_sarif([finding]))
    rule = doc["runs"][0]["tool"]["driver"]["rules"][0]
    assert rule["helpUri"] == (
        "https://github.com/Lunch418/ora2pg-gap-report/blob/main/"
        "docs/research/gap-026-read-only-table.md"
    )


def test_rule_has_no_help_uri_for_a_detector_outside_the_gap_registry():
    # dbms_utl_calls is a classifier over many DBMS_*/UTL_* calls, not a
    # single numbered gap in gap_registry.py -- it must not get a bogus
    # helpUri.
    finding = Finding(
        detector="dbms_utl_calls",
        severity="medium",
        object_name="X",
        line=1,
        snippet="dbms_lob.something",
        message="msg",
    )
    doc = json.loads(to_sarif([finding]))
    rule = doc["runs"][0]["tool"]["driver"]["rules"][0]
    assert "helpUri" not in rule


def test_multiple_messages_from_one_detector_get_separate_rules(sarif_schema):
    # bulk_collect.py attaches one of three distinct static messages
    # (_TYPE_DECL_MESSAGE / _BULK_COLLECT_MESSAGE / _FORALL_MESSAGE)
    # depending on which sub-pattern matched, all under
    # detector="bulk_collect" -- see terminal_report.py's own
    # explanation_counts, which groups by (detector, message) for exactly
    # this reason. compound_trigger_apress.sql triggers two of them (a
    # TYPE...IS TABLE OF declaration and a FORALL), a real regression case
    # for grouping SARIF rules by detector alone: that would attach
    # whichever message came first to a rule shared by both results,
    # misdescribing the other one.
    source = (SAMPLES / "compound_trigger_apress.sql").read_text()
    findings = [f for f in scan_source(source) if f.detector == "bulk_collect"]
    assert len({f.message for f in findings}) >= 2, "fixture must still exercise >=2 distinct messages"

    doc = json.loads(to_sarif(findings))
    jsonschema.validate(doc, sarif_schema)

    rules_by_id = {r["id"]: r for r in doc["runs"][0]["tool"]["driver"]["rules"]}
    assert len(rules_by_id) == len({f.message for f in findings})
    for result in doc["runs"][0]["results"]:
        rule = rules_by_id[result["ruleId"]]
        assert rule["fullDescription"]["text"] == result["message"]["text"]


def test_short_description_does_not_truncate_mid_word_on_a_message_with_ellipsis():
    # Regression: an earlier version derived shortDescription from the
    # first '.'-terminated sentence of `message`, which broke on messages
    # containing a literal '...' very early (e.g. "TYPE ... IS TABLE OF"),
    # producing a nonsensical "TYPE." instead of a real description.
    finding = Finding(
        detector="bulk_collect",
        severity="high",
        object_name="X",
        line=1,
        snippet="s",
        message="TYPE ... IS TABLE OF ... — a local collection type declaration.",
    )
    doc = json.loads(to_sarif([finding]))
    rule = doc["runs"][0]["tool"]["driver"]["rules"][0]
    assert rule["shortDescription"]["text"] == "Bulk collect"
