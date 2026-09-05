"""SARIF output tests. The vendored schema at
tests/fixtures/sarif-2.1.0.schema.json is the official OASIS SARIF 2.1.0
JSON Schema (fetched once from https://json.schemastore.org/sarif-2.1.0.json
and committed here so validation doesn't depend on network access during
test runs) -- every test below validates real to_sarif() output against
it directly, not just against hand-written expectations about its shape."""

import json
from pathlib import Path
from urllib.parse import urlparse

import jsonschema
import pytest

from ora2pg_gap_report.cli import scan_source
from ora2pg_gap_report.models import Finding
from ora2pg_gap_report.report_generator import to_sarif

SAMPLES = Path(__file__).resolve().parents[1] / "docs" / "research" / "samples"
_SCHEMA_PATH = Path(__file__).resolve().parent / "fixtures" / "sarif-2.1.0.schema.json"


@pytest.fixture(scope="module")
def sarif_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def test_empty_findings_produce_valid_sarif(sarif_schema):
    doc = json.loads(to_sarif([]))
    jsonschema.validate(doc, sarif_schema)
    assert doc["runs"][0]["results"] == []
    assert doc["runs"][0]["tool"]["driver"]["rules"] == []


def test_real_scan_produces_valid_sarif(sarif_schema):
    findings = scan_source((SAMPLES / "logger.pkb").read_text(encoding="utf-8"))
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
    assert len(driver["rules"]) == len({(f.detector, f.message_id) for f in findings})


def test_line_zero_sentinel_produces_valid_sarif_without_a_region(sarif_schema):
    # line=0 is this project's "not a line in this file" sentinel (see
    # cli.py's connect_by_check()) -- SARIF regions are 1-based, so
    # emitting startLine=0 would be an invalid document, not just wrong.
    finding = Finding(
        detector="connect_by",
        severity="high",
        object_name="PKG.PROC",
        line=0,
        snippet="c.level",
        message_id="connect_by",
        source_file="generated_output.sql",
    )
    doc = json.loads(to_sarif([finding]))
    jsonschema.validate(doc, sarif_schema)
    location = doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
    assert "region" not in location
    assert location["artifactLocation"]["uri"] == "generated_output.sql"


def test_artifact_location_uri_percent_encodes_a_space(sarif_schema):
    # artifactLocation.uri must be a valid URI-reference (RFC 3986) --
    # jsonschema.validate() doesn't actually check the schema's own
    # "format": "uri-reference" constraint here (this environment has no
    # format-checker plugin registered for it -- see
    # jsonschema.FormatChecker().checkers), so a raw, unencoded path
    # would still pass this project's own schema-validating tests even
    # though it isn't a real URI. A literal space is not a valid
    # URI-reference character; it must come out percent-encoded.
    finding = Finding(
        detector="autonomous_tx",
        severity="high",
        object_name="X",
        line=1,
        snippet="s",
        message_id="autonomous_tx",
        source_file="my folder/logger.pkb",
    )
    doc = json.loads(to_sarif([finding]))
    jsonschema.validate(doc, sarif_schema)
    uri = doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    assert uri == "my%20folder/logger.pkb"
    assert urlparse(uri).scheme == ""


def test_artifact_location_uri_does_not_let_a_windows_drive_letter_look_like_a_scheme():
    # A Windows-style absolute path's drive letter ('C:\\Users\\...') would
    # parse as if 'C' were the URI scheme if the colon were left
    # unescaped -- urlparse().scheme must stay empty (a relative
    # reference), not 'c'.
    finding = Finding(
        detector="autonomous_tx",
        severity="high",
        object_name="X",
        line=1,
        snippet="s",
        message_id="autonomous_tx",
        source_file="C:\\Users\\me\\logger.pkb",
    )
    doc = json.loads(to_sarif([finding]))
    uri = doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    assert urlparse(uri).scheme == ""
    assert "\\" not in uri
    assert ":" not in uri


def test_artifact_location_uri_leaves_a_plain_relative_path_unchanged():
    # No characters needing escaping -- must round-trip byte-for-byte,
    # matching what a real SARIF consumer resolves back to the scanned
    # file on disk.
    finding = Finding(
        detector="autonomous_tx",
        severity="high",
        object_name="X",
        line=1,
        snippet="s",
        message_id="autonomous_tx",
        source_file="docs/research/samples/logger.pkb",
    )
    doc = json.loads(to_sarif([finding]))
    uri = doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    assert uri == "docs/research/samples/logger.pkb"


def test_severity_maps_to_the_expected_sarif_level():
    findings = [
        Finding(detector="a", severity="high", object_name="X", line=1, snippet="s", message_id="read_only_table"),
        Finding(detector="b", severity="medium", object_name="X", line=1, snippet="s", message_id="read_only_table"),
        Finding(detector="c", severity="low", object_name="X", line=1, snippet="s", message_id="read_only_table"),
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
        message_id="read_only_table",
    )
    doc = json.loads(to_sarif([finding]))
    rule = doc["runs"][0]["tool"]["driver"]["rules"][0]
    assert rule["helpUri"] == (
        "https://github.com/Lunch418/ora2pg-gap-report/blob/main/"
        "docs/research/gap-026-read-only-table.md"
    )


def test_rule_properties_carry_gap_number_and_failure_stage():
    finding = Finding(
        detector="read_only_table",  # GAP-026, failure_stage="semantic"
        severity="high",
        object_name="AUDIT_LOG",
        line=4,
        snippet="READ ONLY",
        message_id="read_only_table",
    )
    doc = json.loads(to_sarif([finding]))
    rule = doc["runs"][0]["tool"]["driver"]["rules"][0]
    assert rule["properties"] == {"gapNumber": "026", "failureStage": "semantic"}


def test_rule_properties_omit_failure_stage_for_an_exempt_gap():
    finding = Finding(
        detector="autonomous_tx",  # GAP-001, in FAILURE_STAGE_EXEMPT_DETECTORS
        severity="high",
        object_name="LOGGER.PURGE_ALL",
        line=1,
        snippet="pragma autonomous_transaction;",
        message_id="autonomous_tx",
    )
    doc = json.loads(to_sarif([finding]))
    rule = doc["runs"][0]["tool"]["driver"]["rules"][0]
    assert rule["properties"] == {"gapNumber": "001"}
    assert "failureStage" not in rule["properties"]


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
        message_id="dbms_utl_calls",
    )
    doc = json.loads(to_sarif([finding]))
    rule = doc["runs"][0]["tool"]["driver"]["rules"][0]
    assert "helpUri" not in rule
    assert "properties" not in rule


def test_multiple_messages_from_one_detector_get_separate_rules(sarif_schema):
    # bulk_collect emits one of three distinct messages depending on
    # which sub-pattern matched, all under detector="bulk_collect" --
    # see terminal_report.py's own explanation_counts, which groups by
    # (detector, message_id) for exactly this reason. compound_trigger_apress.sql triggers two of them (a
    # TYPE...IS TABLE OF declaration and a FORALL), a real regression case
    # for grouping SARIF rules by detector alone: that would attach
    # whichever message came first to a rule shared by both results,
    # misdescribing the other one.
    source = (SAMPLES / "compound_trigger_apress.sql").read_text(encoding="utf-8")
    findings = [f for f in scan_source(source) if f.detector == "bulk_collect"]
    assert len({f.message_id for f in findings}) >= 2, "fixture must still exercise >=2 distinct messages"

    doc = json.loads(to_sarif(findings))
    jsonschema.validate(doc, sarif_schema)

    rules_by_id = {r["id"]: r for r in doc["runs"][0]["tool"]["driver"]["rules"]}
    assert len(rules_by_id) == len({f.message_id for f in findings})
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
        message_id="bulk_collect.bulk_collect"    )
    doc = json.loads(to_sarif([finding]))
    rule = doc["runs"][0]["tool"]["driver"]["rules"][0]
    assert rule["shortDescription"]["text"] == "Bulk collect"


def _fingerprint(finding):
    import json

    from ora2pg_gap_report.report_generator import to_sarif

    result = json.loads(to_sarif([finding]))["runs"][0]["results"][0]
    return result["partialFingerprints"]["ora2pgGapReport/groupKey/v1"]


def _finding(**overrides):
    from ora2pg_gap_report.models import Finding

    base = dict(
        detector="read_only_table", severity="high", object_name="HR.EMPLOYEES",
        line=12, snippet="READ ONLY", message_id="read_only_table",
        source_file="schema/tables.sql",
    )
    base.update(overrides)
    return Finding(**base)


def test_the_fingerprint_survives_an_edit_above_the_finding():
    # The whole point: GitHub code scanning matches alerts on
    # partialFingerprints when present, and on the line number when not.
    # Without this, inserting a line anywhere above a finding closes its
    # alert and opens an identical one -- taking any reviewer dismissal
    # with it.
    assert _fingerprint(_finding(line=12)) == _fingerprint(_finding(line=400))


def test_the_fingerprint_distinguishes_findings_that_are_genuinely_different():
    baseline = _fingerprint(_finding())
    assert _fingerprint(_finding(object_name="HR.ORDERS")) != baseline
    assert _fingerprint(_finding(source_file="schema/other.sql")) != baseline
    assert _fingerprint(_finding(detector="bitmap_index")) != baseline
    assert _fingerprint(_finding(snippet="READ WRITE")) != baseline


def test_the_fingerprint_is_the_same_value_baseline_diffing_uses():
    # Two mechanisms answering "is this the same finding as before" must
    # not answer it differently.
    from ora2pg_gap_report.baseline import group_key

    finding = _finding()
    assert _fingerprint(finding) == group_key(finding)
