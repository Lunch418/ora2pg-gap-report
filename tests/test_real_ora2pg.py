"""Tests that run the real `ora2pg` binary.

Everything else in this suite tests this project's own code against
recorded ora2pg behaviour. Nothing tested that the recording still
matches: ora2pg_wrapper.py parses ora2pg's `--estimate_cost` output by
matching its exact comment-line wording, and that module's own docstring
says outright that a future ora2pg release rewording its output would
make these regexes silently stop matching -- counting as "nothing found"
rather than raising. A silent zero is indistinguishable from a clean
package, which is the worst failure mode a tool like this has.

So these run ora2pg for real and assert the parsers still recognise what
comes back. They are skipped without ora2pg on PATH, so a developer
without a Perl toolchain still gets a green suite; the CI job that
installs ora2pg is what makes them run.
"""

import shutil
from pathlib import Path

import pytest

from ora2pg_gap_report import ora2pg_wrapper
from ora2pg_gap_report.gap_registry import verified_ora2pg_versions

pytestmark = [
    pytest.mark.ora2pg,
    pytest.mark.skipif(shutil.which("ora2pg") is None, reason="no ora2pg on PATH"),
]

SAMPLES = Path(__file__).resolve().parent.parent / "docs" / "research" / "samples"


def test_the_installed_version_can_be_read():
    # If this returns None, the version-mismatch warning in cli.py is
    # silently doing nothing on a machine that does have ora2pg.
    assert ora2pg_wrapper.installed_version() is not None


def test_the_installed_version_is_one_the_registry_was_verified_against():
    # Not a correctness requirement for the tool -- it works against other
    # versions, and warns when they differ. It is a requirement for CI: a
    # job pinned to a version the findings were never confirmed on would
    # be testing the parsers against output nobody has checked the
    # research against.
    installed = ora2pg_wrapper.installed_version()
    assert installed in verified_ora2pg_versions(), (
        f"CI has ora2pg {installed}; the registry records findings against "
        f"{sorted(verified_ora2pg_versions())}. Either pin the CI version or "
        "re-verify the gaps and update gap_registry.py."
    )


def test_estimate_cost_produces_output_on_a_real_package():
    output = ora2pg_wrapper.run_estimate_cost(SAMPLES / "logger.pkb", "PACKAGE")
    assert output.strip(), "ora2pg produced no output for a real PACKAGE BODY"


def test_the_per_function_cost_parser_still_matches_real_output():
    # The regression this file exists for: _FUNCTION_COST_RE matching
    # ora2pg's own comment wording.
    output = ora2pg_wrapper.run_estimate_cost(SAMPLES / "logger.pkb", "PACKAGE")
    costs = ora2pg_wrapper.parse_function_costs(output)
    assert costs, "parse_function_costs() found nothing in real ora2pg output"
    # Logger is a large real package; a handful of functions would mean
    # the regex matched some unrelated line rather than the cost block.
    assert len(costs) > 10
    assert all(c.total_cost > 0 for c in costs)
    assert any(c.breakdown for c in costs), "no keyword breakdown was parsed"


def test_the_totals_parser_still_matches_real_output():
    output = ora2pg_wrapper.run_estimate_cost(SAMPLES / "logger.pkb", "PACKAGE")
    totals = ora2pg_wrapper.parse_totals(output)
    assert totals, "parse_totals() found nothing in real ora2pg output"
    name, units, person_days = totals[0]
    assert units > 0
    assert person_days > 0


def test_a_file_with_nothing_of_that_type_yields_no_costs():
    # The other half of the contract: "nothing found" has to be reachable
    # honestly, so that the assertions above mean something.
    output = ora2pg_wrapper.run_estimate_cost(SAMPLES / "logger.pkb", "TRIGGER")
    assert ora2pg_wrapper.parse_function_costs(output) == []


def test_check_connect_by_runs_end_to_end_through_the_cli(capsys, tmp_path):
    # The one CLI path that shells out to ora2pg. Covered here rather than
    # only at the wrapper level because everything between them -- picking
    # the object type from the source, invoking the binary, reading the
    # generated file back, turning it into findings -- is also only ever
    # exercised against a real ora2pg.
    from ora2pg_gap_report.cli import main

    sample = SAMPLES / "connect_by_hierarchy_pkg.sql"
    exit_code = main([str(sample), "--check-connect-by", "--format", "json"])
    captured = capsys.readouterr()

    assert exit_code == 0

    import json

    payload = json.loads(captured.out)
    detectors = {f["detector"] for f in payload["findings"]}
    # The sample is the project's own CONNECT BY fixture; connect_by only
    # reports by analysing ora2pg's generated output, so its presence here
    # proves the whole chain ran.
    assert "connect_by" in detectors, (
        f"--check-connect-by produced no connect_by finding; got {sorted(detectors)}. "
        f"stderr was: {captured.err}"
    )
