import shutil
from pathlib import Path

import pytest

from ora2pg_gap_report import ora2pg_wrapper
from ora2pg_gap_report.ora2pg_wrapper import (
    Ora2PgNotFoundError,
    Ora2PgRunError,
    parse_function_costs,
    parse_totals,
    run_estimate_cost,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLES = Path(__file__).resolve().parents[1] / "docs" / "research" / "samples"


def test_parse_function_costs_from_real_ora2pg_output():
    # Fixture captured from a real run:
    # ora2pg -t PACKAGE -i logger.pkb --estimate_cost
    output = (FIXTURES / "ora2pg_estimate_cost_logger.txt").read_text(encoding="utf-8")
    functions = parse_function_costs(output)
    by_name = {f.name: f for f in functions}

    f = by_name["logger.append_cgi_env"]
    assert f.total_cost == 3.4
    assert f.breakdown == {"CONCAT": 4, "TEST": 2, "SIZE": 1}


def test_parse_function_costs_confirms_pragma_missing_from_breakdown():
    # Direct confirmation of the bug documented in
    # docs/research/step0-show-report-baseline.md section 2: PRAGMA
    # AUTONOMOUS_TRANSACTION sits in the declare section (before BEGIN) and
    # never makes it into ora2pg's own cost breakdown for package
    # functions, even though logger.save_global_context has the pragma and
    # ora2pg visibly generates a dblink wrapper for it elsewhere in the
    # same run.
    output = (FIXTURES / "ora2pg_estimate_cost_logger.txt").read_text(encoding="utf-8")
    functions = parse_function_costs(output)
    by_name = {f.name: f for f in functions}

    f = by_name["logger.save_global_context"]
    assert f.total_cost == 6
    assert f.breakdown == {"TEST": 2, "SIZE": 1, "DBMS_": 1}
    assert "PRAGMA" not in f.breakdown


def test_parse_totals_for_package_mode():
    output = (FIXTURES / "ora2pg_estimate_cost_logger.txt").read_text(encoding="utf-8")
    assert parse_totals(output) == [("logger", 225.1, 3.0)]


def test_parse_totals_returns_one_entry_per_package_in_a_multi_package_run():
    output = (
        "-- Total estimated cost for package pkg_one: 6 units, 1 person-day(s)\n"
        "-- Total estimated cost for package pkg_two: 6 units, 1 person-day(s)\n"
    )
    assert parse_totals(output) == [("pkg_one", 6.0, 1.0), ("pkg_two", 6.0, 1.0)]


def test_parse_function_costs_and_totals_for_standalone_function_mode():
    # -t FUNCTION/-t PROCEDURE format differs from -t PACKAGE: no "total"
    # before "estimated cost", and the totals line has no package name.
    output = (FIXTURES / "ora2pg_estimate_cost_standalone_function.sql").read_text(encoding="utf-8")

    functions = parse_function_costs(output)
    assert len(functions) == 1
    assert functions[0].name == "get_org_chart_standalone"
    assert functions[0].total_cost == 6.2

    assert parse_totals(output) == [(None, 6.2, 1.0)]


def test_parse_function_costs_empty_input_returns_empty_list():
    assert parse_function_costs("") == []


def test_parse_totals_returns_empty_list_when_absent():
    assert parse_totals("nothing relevant here") == []


def test_run_estimate_cost_raises_clear_error_when_ora2pg_not_installed():
    with pytest.raises(Ora2PgNotFoundError):
        run_estimate_cost(
            SAMPLES / "logger.pkb", "PACKAGE", ora2pg_bin="definitely-not-a-real-binary"
        )


@pytest.mark.skipif(shutil.which("ora2pg") is None, reason="ora2pg not installed on PATH")
def test_run_estimate_cost_live_integration_on_logger():
    output = run_estimate_cost(SAMPLES / "logger.pkb", "PACKAGE")
    functions = parse_function_costs(output)
    names = {f.name for f in functions}
    assert "logger.save_global_context" in names


def test_installed_version_parses_the_banner(monkeypatch):
    import subprocess

    def fake_run(cmd, **kwargs):
        assert cmd[1] == "--version"
        return subprocess.CompletedProcess(cmd, 0, stdout="Ora2Pg v25.0\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert ora2pg_wrapper.installed_version() == "25.0"


def test_installed_version_also_looks_at_stderr(monkeypatch):
    # Some builds print the banner there; assuming stdout would report
    # "unknown" for a perfectly working install.
    import subprocess

    monkeypatch.setattr(
        subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="", stderr="Ora2Pg v24.3\n"),
    )
    assert ora2pg_wrapper.installed_version() == "24.3"


def test_installed_version_is_none_when_ora2pg_is_absent():
    assert ora2pg_wrapper.installed_version("definitely-not-a-real-binary-xyz") is None


def test_installed_version_is_none_rather_than_a_guess_on_unrecognized_output(monkeypatch):
    # Reporting a wrong version would be worse than reporting none: the
    # check exists to tell the user their ora2pg differs from the one the
    # findings were verified against.
    import subprocess

    monkeypatch.setattr(
        subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="no version here\n", stderr=""),
    )
    assert ora2pg_wrapper.installed_version() is None


def test_a_failure_reports_ora2pgs_stdout_when_stderr_is_empty(monkeypatch, tmp_path):
    # ora2pg writes its fatal errors to stdout and exits 1 with stderr
    # empty -- "FATAL: can't find configuration file
    # /etc/ora2pg/ora2pg.conf" is the most common one there is. Reporting
    # stderr alone left the user with a bare exit code and no reason.
    import subprocess

    monkeypatch.setattr(
        subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 1,
            stdout="FATAL: can't find configuration file /etc/ora2pg/ora2pg.conf\n"
                   + "\n".join(f"    -{c} | --flag{c}" for c in "abcdefghij"),
            stderr="",
        ),
    )
    with pytest.raises(Ora2PgRunError) as excinfo:
        ora2pg_wrapper.run_estimate_cost(tmp_path / "x.sql", "PACKAGE")
    message = str(excinfo.value)
    assert "can't find configuration file" in message
    # ora2pg follows the fatal line with its whole usage screen; a hundred
    # lines of flag documentation is not an error message.
    assert message.count("\n") <= 6


def test_a_failure_still_prefers_stderr_when_there_is_some(monkeypatch, tmp_path):
    import subprocess

    monkeypatch.setattr(
        subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 1, stdout="some progress output", stderr="DBI connect failed",
        ),
    )
    with pytest.raises(Ora2PgRunError, match="DBI connect failed"):
        ora2pg_wrapper.run_estimate_cost(tmp_path / "x.sql", "PACKAGE")
