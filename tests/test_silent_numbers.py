"""GAP-130..133: numbers and SUBSTR that load and then compute something
else -- on source checked against a live Oracle 23ai and the real
ora2pg 25.0 output recorded in tests/fixtures/silent_numbers/, and,
under the docker marker, what PostgreSQL 16 makes of that output."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ora2pg_gap_report.core import scan_source
from ora2pg_gap_report.detectors.integer_division import find_integer_division
from ora2pg_gap_report.detectors.number_as_float import find_number_as_float
from ora2pg_gap_report.detectors.number_without_precision import find_number_without_precision
from ora2pg_gap_report.detectors.substr_start import find_substr_start

FIXTURES = Path(__file__).parent / "fixtures" / "silent_numbers"
SAMPLES = Path(__file__).resolve().parent.parent / "docs" / "research" / "samples"


def _read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


TABLES = _read("oracle_tables.sql")
FUNCTIONS = _read("oracle_functions.sql")


def _found(detector, source):
    return [(f.object_name, f.line, f.snippet) for f in detector(source)]


# --- GAP-130: NUMBER without precision -------------------------------------------


def test_number_without_precision_once_per_file():
    assert _found(find_number_without_precision, TABLES) == [("GX_PRICES", 1, "id NUMBER")]
    assert _found(find_number_without_precision, FUNCTIONS) == [("GX_N1", 1, "RETURN NUMBER")]


@pytest.mark.parametrize(
    "declaration",
    ["v NUMBER;", "p IN OUT NOCOPY NUMBER", "c CONSTANT NUMBER := 1;", "TYPE t IS TABLE OF NUMBER;", "SUBTYPE s IS NUMBER;"],
)
def test_number_without_precision_shapes(declaration):
    assert find_number_without_precision(f"CREATE OR REPLACE PACKAGE p AS\n  {declaration}\nEND p;\n/\n")


@pytest.mark.parametrize(
    "text",
    [
        "v NUMBER(10);",
        "v NUMBER(10,2);",
        "v NUMBER(*,2);",
        "x := TO_NUMBER(s);",
        "v t.c%TYPE;",
        "-- v NUMBER;",
        "x := 'v NUMBER';",
        "SELECT CAST(x AS NUMBER) INTO y FROM dual;",
    ],
)
def test_number_without_precision_leaves_the_rest_alone(text):
    assert find_number_without_precision(f"CREATE OR REPLACE PROCEDURE p IS\nBEGIN\n  {text}\nEND;\n/\n") == []


# --- GAP-131: NUMBER(p,s) and FLOAT as floating point ---------------------------


def test_number_as_float_once_per_file():
    assert _found(find_number_as_float, TABLES) == [("GX_PAY", 2, "amount NUMBER(10,2)")]
    assert _found(find_number_as_float, FUNCTIONS) == [("GX_F1", 13, "a NUMBER(10,2)")]


@pytest.mark.parametrize(
    ("declaration", "flagged"),
    [
        ("v NUMBER(5,2);", True),  # real, in PL/SQL
        ("v NUMBER(15,2);", True),
        ("v NUMBER(16,2);", False),  # decimal(16,2)
        ("v NUMBER(5,4);", True),
        ("v NUMBER(2,4);", False),  # numeric
        ("v NUMBER(*,2);", False),  # decimal(38,2)
        ("v NUMBER(10,0);", False),
        ("v FLOAT;", True),
        ("v BINARY_DOUBLE;", False),  # IEEE in Oracle too
    ],
)
def test_number_as_float_follows_ora2pg_mapping(declaration, flagged):
    source = f"CREATE OR REPLACE PROCEDURE p IS\n  {declaration}\nBEGIN\n  NULL;\nEND;\n/\n"
    assert bool(find_number_as_float(source)) is flagged


def test_a_small_scaled_column_becomes_decimal_and_is_not_flagged():
    assert find_number_as_float("CREATE TABLE t (a NUMBER(5,2), b NUMBER(6,2));") == []
    assert find_number_as_float("CREATE TABLE t (a NUMBER(5,2), b NUMBER(7,2));")


# --- GAP-132: integer division ------------------------------------------------------


def test_integer_division_in_the_checked_source():
    assert _found(find_integer_division, FUNCTIONS) == [
        ("GX_D1", 31, "7 / 2"),
        ("GX_D1", 31, "b / 2"),
        ("GX_D1", 31, "e / 2"),
    ]  # gx_n2's p / 4 is GAP-130's: p is a NUMBER


def test_integer_division_shapes_and_scope():
    source = """CREATE OR REPLACE PACKAGE BODY pkg AS
  g_count PLS_INTEGER := 0;
  FUNCTION f(n INTEGER, m NUMBER) RETURN NUMBER IS
    i NUMBER(5) := n;
    x NUMBER(10,2) := 1;
    big NUMBER(20) := 1;
  BEGIN
    RETURN i / n + g_count / 2 + 100 / i
         + x / 2 + m / 2 + big / 2 + i / 2.0 + TRUNC(i / 2) + i / x + f2(i) / 2;
  END f;
  FUNCTION g RETURN NUMBER IS
  BEGIN
    RETURN i / 2;
  END g;
END pkg;
/
"""
    assert [(o, s) for o, _, s in _found(find_integer_division, source)] == [
        ("PKG.F", "i / n"),
        ("PKG.F", "g_count / 2"),
        ("PKG.F", "100 / i"),
    ]  # i in PKG.G is not PKG.F's


def test_integer_division_found_in_logger():
    found = _found(find_integer_division, (SAMPLES / "logger.pkb").read_text(encoding="utf-8"))
    assert [(line, snippet) for _, line, snippet in found] == [(553, "1 / 1440"), (555, "1 / 24")]


def test_integer_division_found_again_in_ora2pg_output():
    # --verify reruns the detector on the output: bigint/integer are read --
    # and there gx_n2's p / 4 is an integer division too, p being bigint.
    assert sorted(s for _, _, s in _found(find_integer_division, _read("ora2pg_FUNCTION_output.sql"))) == [
        "7 / 2",
        "b / 2",
        "e / 2",
        "p / 4",
    ]


# --- GAP-133: SUBSTR from 0 or a negative position ---------------------------------


def test_substr_start_in_the_checked_source():
    assert _found(find_substr_start, FUNCTIONS) == [
        ("GX_S1", 36, "SUBSTR(..., 0, ...)"),
        ("GX_S1", 36, "SUBSTR(..., -3)"),
        ("GX_S1", 36, "SUBSTR(..., -3, ...)"),
    ]  # SUBSTR(p, 0) and SUBSTR(p, 2, 2) are the same in both


def test_substr_start_found_in_file_util():
    found = _found(find_substr_start, (SAMPLES / "file_util_pkg.pkb").read_text(encoding="utf-8"))
    assert [(line, snippet) for _, line, snippet in found] == [(39, "SUBSTR(..., -1)"), (51, "SUBSTR(..., -1)")]


@pytest.mark.parametrize(
    "call",
    ["SUBSTR(s, 1, 3)", "SUBSTR(s, v_pos)", "SUBSTR(s, 0)", "SUBSTRB(s, -1)", "pkg.SUBSTR(s, -1)", "SUBSTR(s, 10 - 1)"],
)
def test_substr_start_leaves_the_rest_alone(call):
    assert find_substr_start(f"BEGIN\n  x := {call};\nEND;\n") == []


def test_all_four_are_wired_into_the_oracle_scan():
    found = {f.detector for f in scan_source(TABLES + FUNCTIONS, dialect="oracle")}
    assert {"number_without_precision", "number_as_float", "integer_division", "substr_start"} <= found


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


def _asserts(*conditions):
    return "".join(f"DO $$ BEGIN ASSERT {c}; END $$;\n" for c in conditions)


SETUP = (
    "INSERT INTO gx_prices VALUES (1, 9.99, 1), (2, 0.25, 2);\n"
    "INSERT INTO gx_pay SELECT g, 0.1, 0.0001 FROM generate_series(1, 10) g;\n"
)
# What Oracle 23ai returned for the same calls on the same rows.
AS_IN_ORACLE = _asserts(
    "(SELECT sum(price) FROM gx_prices) = 10.24",
    "gx_n1() = 5",
    "gx_n2(10) = 2.5",
    "gx_f1() = 'equal'",
    "gx_f2() = '1'",
    "gx_d1(7) = '3.5|4|3.5'",
    "gx_s1('abcdef') = 'abc|def|de|abcdef|bc'",
)
# What PostgreSQL 16 returns.
AS_IN_POSTGRESQL = _asserts(
    "(SELECT sum(price) FROM gx_prices) = 10",
    "gx_n1() = 6",
    "gx_n2(10) = 2",
    "gx_f1() = 'not equal'",
    "gx_f2() = '0.9999999999999999'",
    "gx_d1(7) = '3|3|3'",
    "gx_s1('abcdef') = 'ab|abcdef||abcdef|bc'",
)


@pytest.mark.docker
@pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")
def test_the_output_loads_and_then_computes_something_else(tmp_path):
    output = (_read("ora2pg_TABLE_output.sql"), _read("ora2pg_FUNCTION_output.sql"))
    (tmp_path / "oracle").mkdir()
    errors = _load(tmp_path / "oracle", *output, SETUP, AS_IN_ORACLE)
    assert [e.sqlstate for e in errors] == ["P0004"] * 7  # every one differs, none fails to load
    (tmp_path / "postgresql").mkdir()
    assert _load(tmp_path / "postgresql", *output, SETUP, AS_IN_POSTGRESQL) == ()


@pytest.mark.parametrize("division", ["10 / 2", "i / 0", "7 / 0"])
def test_integer_division_that_is_the_same_in_both_is_left_alone(division):
    source = f"CREATE OR REPLACE PROCEDURE p IS\n  i PLS_INTEGER := 7;\nBEGIN\n  i := {division};\nEND;\n/\n"
    assert find_integer_division(source) == []
