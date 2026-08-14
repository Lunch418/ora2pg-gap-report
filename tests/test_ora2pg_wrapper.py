import shutil
from pathlib import Path

import pytest

from src.ora2pg_wrapper import (
    Ora2PgNotFoundError,
    parse_function_costs,
    parse_totals,
    run_estimate_cost,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLES = Path(__file__).resolve().parents[1] / "docs" / "research" / "samples"


def test_parse_function_costs_from_real_ora2pg_output():
    # Fixture captured from a real run:
    # ora2pg -t PACKAGE -i logger.pkb --estimate_cost
    output = (FIXTURES / "ora2pg_estimate_cost_logger.txt").read_text()
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
    output = (FIXTURES / "ora2pg_estimate_cost_logger.txt").read_text()
    functions = parse_function_costs(output)
    by_name = {f.name: f for f in functions}

    f = by_name["logger.save_global_context"]
    assert f.total_cost == 6
    assert f.breakdown == {"TEST": 2, "SIZE": 1, "DBMS_": 1}
    assert "PRAGMA" not in f.breakdown


def test_parse_totals_for_package_mode():
    output = (FIXTURES / "ora2pg_estimate_cost_logger.txt").read_text()
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
    output = (FIXTURES / "ora2pg_estimate_cost_standalone_function.sql").read_text()

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
