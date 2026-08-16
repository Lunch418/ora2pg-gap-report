import json
from pathlib import Path

import jsonschema
import pytest

from ora2pg_gap_report.baseline import save_baseline
from ora2pg_gap_report.cli import scan_source
from ora2pg_gap_report.report_generator import to_json

SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"
SAMPLES = Path(__file__).resolve().parents[1] / "docs" / "research" / "samples"


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / name).read_text())


@pytest.fixture(scope="module")
def report_schema() -> dict:
    return _load_schema("report.schema.json")


@pytest.fixture(scope="module")
def baseline_schema() -> dict:
    return _load_schema("baseline.schema.json")


def test_report_schema_itself_is_valid_json_schema(report_schema):
    jsonschema.Draft202012Validator.check_schema(report_schema)


def test_baseline_schema_itself_is_valid_json_schema(baseline_schema):
    jsonschema.Draft202012Validator.check_schema(baseline_schema)


def test_real_json_report_validates_against_report_schema(report_schema):
    findings = scan_source((SAMPLES / "logger.pkb").read_text())
    assert findings, "expected at least one finding to make this a meaningful check"
    report = json.loads(to_json(findings))
    jsonschema.validate(report, report_schema)


def test_empty_json_report_validates_against_report_schema(report_schema):
    jsonschema.validate([], report_schema)


def test_real_baseline_snapshot_validates_against_baseline_schema(tmp_path, baseline_schema):
    findings = scan_source((SAMPLES / "logger.pkb").read_text())
    path = tmp_path / "baseline.json"
    save_baseline(findings, path)

    snapshot = json.loads(path.read_text())
    jsonschema.validate(snapshot, baseline_schema)


def test_empty_baseline_snapshot_validates_against_baseline_schema(tmp_path, baseline_schema):
    path = tmp_path / "empty_baseline.json"
    save_baseline([], path)
    snapshot = json.loads(path.read_text())
    jsonschema.validate(snapshot, baseline_schema)


def test_report_schema_rejects_an_unknown_severity(report_schema):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            [
                {
                    "detector": "x",
                    "severity": "critical",  # not a real severity in this project
                    "object_name": "X",
                    "line": 1,
                    "snippet": "x",
                    "message": "x",
                    "source_file": "x.sql",
                }
            ],
            report_schema,
        )


def test_baseline_schema_rejects_a_mismatched_schema_version(baseline_schema):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"schema_version": 2, "findings": []}, baseline_schema)
