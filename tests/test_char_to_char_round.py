"""GAP-139..142: TO_CHAR of an expression, TO_CHAR without a format,
CHAR(n) and ROUND of a date -- on source checked against a live Oracle
23ai and the real ora2pg 25.0 output recorded in
tests/fixtures/char_to_char_round/, and, under the docker marker, what
PostgreSQL 16 makes of that output."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ora2pg_gap_report.core import scan_source
from ora2pg_gap_report.detectors.char_semantics import find_char_semantics
from ora2pg_gap_report.detectors.round_date import find_round_date
from ora2pg_gap_report.detectors.to_char_default_format import find_to_char_default_format
from ora2pg_gap_report.detectors.to_char_operator import find_to_char_operator

FIXTURES = Path(__file__).parent / "fixtures" / "char_to_char_round"
SAMPLES = Path(__file__).resolve().parent.parent / "docs" / "research" / "samples"


def _read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


TABLES = _read("oracle_tables.sql")
FUNCTIONS = _read("oracle_functions.sql")


def _found(detector, source):
    return [(f.object_name, f.line, f.snippet) for f in detector(source)]


def _routine(body, declarations=""):
    return (
        "CREATE OR REPLACE FUNCTION f(n NUMBER, d DATE, t TIMESTAMP, s VARCHAR2) RETURN VARCHAR2 IS\n"
        f"{declarations}BEGIN\n  {body}\nEND;\n/\n"
    )


# --- GAP-139: TO_CHAR of an expression written without spaces --------------------


def test_to_char_operator_in_the_checked_source():
    assert _found(find_to_char_operator, FUNCTIONS) == [("GX_R1", 3, "TO_CHAR(a/b)"), ("GX_R1", 3, "TO_CHAR(-a)")]


@pytest.mark.parametrize(
    ("call", "flagged"),
    [
        ("TO_CHAR(n+1)", True),
        ("TO_CHAR(n*2)", True),
        ("TO_CHAR(n-1)", True),
        ("TO_CHAR(n + 1)", False),  # ora2pg puts it in parentheses
        ("TO_CHAR(ABS(n-1))", False),  # the cast applies to the whole call
        ("TO_CHAR(n)", False),
        ("TO_CHAR(n/2, '990.99')", False),  # a format: to_char stays
    ],
)
def test_to_char_operator_shapes(call, flagged):
    assert bool(find_to_char_operator(_routine(f"RETURN {call};"))) is flagged


# --- GAP-140: TO_CHAR without a format of a date or a fraction ----------------------


def test_to_char_default_format_in_the_checked_source():
    assert _found(find_to_char_default_format, FUNCTIONS) == [("GX_R2", 10, "TO_CHAR(v)"), ("GX_R2", 10, "TO_CHAR(d)")]


@pytest.mark.parametrize(
    ("call", "flagged"),
    [
        ("TO_CHAR(d)", True),
        ("TO_CHAR(t)", True),
        ("TO_CHAR(SYSDATE)", True),
        ("TO_CHAR(0.5)", True),
        ("TO_CHAR(d, 'YYYY-MM-DD')", False),
        ("TO_CHAR(n)", False),  # bigint: the same digits
        ("TO_CHAR(s)", False),
        ("TO_CHAR(some_column)", False),
    ],
)
def test_to_char_default_format_shapes(call, flagged):
    assert bool(find_to_char_default_format(_routine(f"RETURN {call};"))) is flagged


def test_an_overload_takes_its_own_parameter_type():
    # OraOpenSource Logger: tochar(p_val NUMBER) is to_char(p_val); the
    # DATE overloads pass a format.
    assert find_to_char_default_format((SAMPLES / "logger.pkb").read_text(encoding="utf-8")) == []


# --- GAP-141: CHAR(n) ------------------------------------------------------------------


def test_char_semantics_once_per_file():
    assert _found(find_char_semantics, TABLES) == [("GX_CODES", 1, "code CHAR(5)")]
    assert _found(find_char_semantics, FUNCTIONS) == [("GX_R3", 14, "c CHAR(5)")]


@pytest.mark.parametrize(
    ("declaration", "flagged"),
    [
        ("c CHAR(2);", True),
        ("c NCHAR(10);", True),
        ("c CHAR(10 BYTE);", True),
        ("c CHAR(1);", False),
        ("c CHAR;", False),
        ("c VARCHAR2(10);", False),
        ("c NVARCHAR2(10);", False),
    ],
)
def test_char_semantics_shapes(declaration, flagged):
    assert bool(find_char_semantics(_routine("RETURN NULL;", f"  {declaration}\n"))) is flagged


# --- GAP-142: ROUND of a date -----------------------------------------------------------


def test_round_date_in_the_checked_source():
    assert _found(find_round_date, FUNCTIONS) == [("GX_R4", 24, "ROUND(d, 'MM')"), ("GX_R4", 24, "ROUND(d)")]


@pytest.mark.parametrize(
    ("call", "flagged"),
    [
        ("ROUND(t)", True),
        ("ROUND(SYSDATE)", True),
        ("ROUND(some_column, 'DD')", True),  # only a date's ROUND takes a format
        ("ROUND(n)", False),
        ("ROUND(n, 2)", False),
        ("ROUND(some_column)", False),
    ],
)
def test_round_date_shapes(call, flagged):
    assert bool(find_round_date(_routine(f"RETURN {call};"))) is flagged


def test_all_four_are_wired_into_the_oracle_scan():
    found = {f.detector for f in scan_source(TABLES + FUNCTIONS, dialect="oracle")}
    assert {"to_char_operator", "to_char_default_format", "char_semantics", "round_date"} <= found


# --- PostgreSQL 16 -------------------------------------------------------------


def _docker_usable():
    if not sys.platform.startswith("linux") or shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _load(tmp_path, *texts):
    from ora2pg_gap_report.load_check import parse_target, run_load_check

    files = []
    for i, text in enumerate(texts):
        path = tmp_path / f"{i}.sql"
        path.write_text(text, encoding="utf-8")
        files.append(path)
    return run_load_check(files, parse_target("docker")).errors


def _statements(*lines):
    return "".join(f"DO $$ BEGIN {line}; END $$;\n" for line in lines)


SETUP = "INSERT INTO gx_codes VALUES (1, 'AB', 'Y');\n"
# What Oracle 23ai returned (gx_r1(1, 4) and gx_r4 fail in PostgreSQL first).
AS_IN_ORACLE = _statements(
    "ASSERT gx_r2(1) = '.5|17-MAR-26'",
    "ASSERT gx_r3() = '5|AB   x|not equal|5'",
)
AS_IN_POSTGRESQL = _statements(
    "ASSERT gx_r2(1) = '0.5|2026-03-17 00:00:00'",
    "ASSERT gx_r3() = '2|ABx|equal|2'",
)
FAILING_CALLS = _statements("PERFORM gx_r1(1, 4)", "PERFORM gx_r4('2026-03-17 15:00')")


@pytest.mark.docker
@pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")
def test_the_output_loads_and_then_fails_or_differs(tmp_path):
    output = (_read("ora2pg_TABLE_output.sql"), _read("ora2pg_FUNCTION_output.sql"))
    (tmp_path / "oracle").mkdir()
    errors = _load(tmp_path / "oracle", *output, SETUP, AS_IN_ORACLE, FAILING_CALLS)
    assert [e for e in errors if e.file.endswith(("0.sql", "1.sql"))] == []  # everything loads
    assert [e.sqlstate for e in errors if e.file.endswith("3.sql")] == ["P0004", "P0004"]  # differs
    assert [e.sqlstate for e in errors if e.file.endswith("4.sql")] == ["42883", "42883"]  # bigint / text, round(timestamp)
    (tmp_path / "postgresql").mkdir()
    errors = _load(tmp_path / "postgresql", *output, SETUP, AS_IN_POSTGRESQL)
    assert errors == ()
