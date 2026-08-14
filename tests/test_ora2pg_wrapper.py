import shutil
from pathlib import Path

import pytest

from src.ora2pg_wrapper import (
    Ora2PgNotFoundError,
    parse_function_costs,
    parse_package_total,
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


def test_parse_package_total():
    output = (FIXTURES / "ora2pg_estimate_cost_logger.txt").read_text()
    assert parse_package_total(output) == ("logger", 225.1, 3.0)


def test_parse_function_costs_empty_input_returns_empty_list():
    assert parse_function_costs("") == []


def test_parse_package_total_returns_none_when_absent():
    assert parse_package_total("nothing relevant here") is None


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
