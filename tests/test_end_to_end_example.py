"""examples/end-to-end/ commits the outputs of its own walkthrough --
baseline.json and the two verification_*.json files -- so a reader can
follow along without running anything. Nothing used to check them, and
when baseline.py's SCHEMA_VERSION moved to 3 the committed baseline stayed
at 2: run_demo.sh then failed at its --verify step with exit code 2 while
every test stayed green. These tests regenerate each committed file the
way the example's README says it was produced, from the example's own
directory exactly like run_demo.sh does, and require the result to match
the file on disk."""

import json
from pathlib import Path

import pytest

from ora2pg_gap_report.cli import main

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "end-to-end"


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_committed_baseline_is_what_scanning_the_oracle_source_saves_today(
    tmp_path, monkeypatch, capsys
):
    # From the example directory, like run_demo.sh: group_key() hashes the
    # source path relative to the cwd, so any other cwd produces different
    # keys for the very same findings.
    monkeypatch.chdir(EXAMPLE)
    saved = tmp_path / "baseline.json"
    exit_code = main(["oracle/", "--save", str(saved), "--lang", "en", "--format", "json"])
    capsys.readouterr()

    assert exit_code == 0
    assert _read_json(saved) == _read_json(EXAMPLE / "baseline.json")


@pytest.mark.parametrize(
    ("generated_dir", "committed"),
    [
        ("generated/", "verification_before_fix.json"),
        ("generated_fixed/", "verification_after_fix.json"),
    ],
)
def test_committed_verification_is_what_verify_prints_today(
    generated_dir, committed, monkeypatch, capsys
):
    monkeypatch.chdir(EXAMPLE)
    exit_code = main(
        ["--verify", "--baseline", "baseline.json", generated_dir, "--lang", "en", "--format", "json"]
    )
    captured = capsys.readouterr()

    assert exit_code == 0, captured.err
    assert json.loads(captured.out) == _read_json(EXAMPLE / committed)
