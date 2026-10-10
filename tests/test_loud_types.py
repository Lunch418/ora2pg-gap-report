"""GAP-134..138: TRUNC of a number, FLOAT(n), PL/SQL integer subtypes,
INSTR with a position, DATE arithmetic -- on source checked against a
live Oracle 23ai and the real ora2pg 25.0 output recorded in
tests/fixtures/loud_types/, and, under the docker marker, how PostgreSQL
16 fails on that output (and loads after --fix where --fix applies)."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ora2pg_gap_report.autofix import fix_double_precision_length, fix_plsql_integer_subtypes
from ora2pg_gap_report.core import scan_source
from ora2pg_gap_report.detectors.date_arithmetic import find_date_arithmetic
from ora2pg_gap_report.detectors.float_precision import find_float_precision
from ora2pg_gap_report.detectors.instr_occurrence import find_instr_occurrence
from ora2pg_gap_report.detectors.plsql_integer_subtype import find_plsql_integer_subtype
from ora2pg_gap_report.detectors.trunc_number import find_trunc_number

FIXTURES = Path(__file__).parent / "fixtures" / "loud_types"
SAMPLES = Path(__file__).resolve().parent.parent / "docs" / "research" / "samples"


def _read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


SOURCE = _read("oracle_functions.sql")
OUTPUT = _read("ora2pg_FUNCTION_output.sql")


def _found(detector, source):
    return [(f.object_name, f.line, f.snippet) for f in detector(source)]


def _routine(body, declarations="", params="n NUMBER, d DATE, t TIMESTAMP, s VARCHAR2"):
    return f"CREATE OR REPLACE FUNCTION f({params}) RETURN NUMBER IS\n{declarations}BEGIN\n  {body}\nEND;\n/\n"


# --- GAP-134: TRUNC of a number ---------------------------------------------------


def test_trunc_number_in_the_checked_source():
    assert _found(find_trunc_number, SOURCE) == [("GX_L1", 3, "TRUNC(n / 3)"), ("GX_L2", 8, "TRUNC(n, 2)")]


@pytest.mark.parametrize(
    ("call", "flagged"),
    [
        ("TRUNC(n)", True),
        ("TRUNC(2.75)", True),
        ("TRUNC(ABS(n))", True),
        ("TRUNC(TO_NUMBER(s))", True),
        ("TRUNC(n * 1.5)", True),
        ("TRUNC(d)", False),
        ("TRUNC(SYSDATE)", False),
        ("TRUNC(d, 'MM')", False),
        ("TRUNC(t)", False),
        ("TRUNC(some_column)", False),
        ("pkg.TRUNC(n)", False),
    ],
)
def test_trunc_number_only_when_the_argument_is_a_number(call, flagged):
    assert bool(find_trunc_number(_routine(f"RETURN {call};"))) is flagged


def test_trunc_number_found_in_logger():
    found = _found(find_trunc_number, (SAMPLES / "logger.pkb").read_text(encoding="utf-8"))
    assert [(line, snippet) for _, line, snippet in found] == [(562, "TRUNC((p_date_stop-p_date_start)/7)")]


# --- GAP-135: FLOAT(n) ---------------------------------------------------------------


def test_float_precision_in_plsql_only():
    assert _found(find_float_precision, SOURCE) == [("GX_L3", 12, "f FLOAT(10)")]
    assert find_float_precision("CREATE TABLE t (a FLOAT(10), b FLOAT);") == []  # double precision, loads
    assert find_float_precision(_routine("RETURN 1;", "  f FLOAT := 1;\n")) == []


def test_float_precision_fix():
    fixed, count = fix_double_precision_length(OUTPUT)
    assert count == 1 and "f double precision := n;" in fixed
    assert fix_double_precision_length(fixed) == (fixed, 0)


# --- GAP-136: PL/SQL integer subtypes ----------------------------------------------


def test_plsql_integer_subtype_in_the_checked_source():
    assert _found(find_plsql_integer_subtype, SOURCE) == [
        ("GX_L4", 18, "s SIMPLE_INTEGER"),
        ("GX_L4", 19, "k NATURAL"),
        ("GX_L4", 20, "p POSITIVE"),
        ("GX_L4", 21, "g SIGNTYPE"),
    ]


def test_plsql_integer_subtype_shapes():
    source = _routine("RETURN 1;", "  a NATURALN := 0;\n  b POSITIVEN := 1;\n  c PLS_INTEGER;\n  positive BOOLEAN;\n")
    assert [s for _, _, s in _found(find_plsql_integer_subtype, source)] == ["a NATURALN", "b POSITIVEN"]
    spec = "CREATE OR REPLACE PACKAGE p AS\n  g_n NATURAL := 0;\nEND p;\n/\n"
    assert find_plsql_integer_subtype(spec) == []  # package_state's


def test_plsql_integer_subtype_fix():
    fixed, count = fix_plsql_integer_subtypes(OUTPUT)
    assert count == 4
    for line in ("s integer := 1;", "k integer := 2;", "p integer := 3;", "g smallint := -1;"):
        assert line in fixed
    assert fix_plsql_integer_subtypes(fixed) == (fixed, 0)


def test_plsql_integer_subtype_fix_leaves_names_and_strings_alone():
    text = "  positive boolean := true;\n  x := 'NATURAL';\n  natural_count integer;\n"
    assert fix_plsql_integer_subtypes(text) == (text, 0)


# --- GAP-137: INSTR with a position or an occurrence --------------------------------


def test_instr_occurrence_in_the_checked_source():
    assert _found(find_instr_occurrence, SOURCE) == [
        ("GX_L5", 28, "INSTR(..., ..., -1)"),
        ("GX_L5", 28, "INSTR(..., ..., 1, 2)"),
    ]


def test_two_argument_instr_is_converted_and_not_flagged():
    assert find_instr_occurrence(_routine("RETURN INSTR(s, '.');")) == []


def test_instr_occurrence_found_in_samples():
    found = _found(find_instr_occurrence, (SAMPLES / "file_util_pkg.pkb").read_text(encoding="utf-8"))
    assert [line for _, line, _ in found] == [98, 134, 171]


# --- GAP-138: DATE arithmetic -----------------------------------------------------------


def test_date_arithmetic_in_the_checked_source():
    assert _found(find_date_arithmetic, SOURCE) == [
        ("GX_L6", 34, "d1 - d2"),
        ("GX_L7", 39, "d + 1"),
        ("GX_L7", 41, "TRUNC(d) - 7"),
    ]


@pytest.mark.parametrize(
    ("expression", "flagged"),
    [
        ("d + 1", True),
        ("d - 0.5", True),
        ("d + 1/24", True),
        ("d + n", True),
        ("TRUNC(SYSDATE) - 7", True),
        ("SYSDATE - d", True),
        ("t + 1", True),  # a date in Oracle, an error in PostgreSQL
        ("t - t", False),  # an interval in both
        ("d - t", False),
        ("SYSDATE + 1", False),  # ora2pg writes an interval
        ("n + 1", False),
        ("d + INTERVAL '1' DAY", False),
        ("col_date + 1", False),  # a column: its type is not known
    ],
)
def test_date_arithmetic_shapes(expression, flagged):
    assert bool(find_date_arithmetic(_routine(f"RETURN {expression};"))) is flagged


def test_date_arithmetic_found_in_logger():
    found = _found(find_date_arithmetic, (SAMPLES / "logger.pkb").read_text(encoding="utf-8"))
    assert [line for _, line, _ in found] == list(range(553, 564))


def test_all_five_are_wired_into_the_oracle_scan():
    found = {f.detector for f in scan_source(SOURCE, dialect="oracle")}
    assert {"trunc_number", "float_precision", "plsql_integer_subtype", "instr_occurrence", "date_arithmetic"} <= found


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


# One statement per call, so each failure is its own error.
CALLS = "".join(
    f"DO $$ BEGIN PERFORM {call}; END $$;\n"
    for call in (
        "gx_l1(10)",
        "gx_l2(3)",
        "gx_l5('a.b.c')",
        "gx_l6('2026-01-03', '2026-01-01')",
        "gx_l7('2026-01-10')",
    )
)


@pytest.mark.docker
@pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")
def test_the_output_fails_to_load_or_to_run(tmp_path):
    errors = _load(tmp_path, OUTPUT, CALLS)
    loading = [(e.sqlstate, e.detector) for e in errors if e.file.endswith("0.sql")]
    assert loading == [("42601", "float_precision"), ("42704", "plsql_integer_subtype")]
    running = [e.sqlstate for e in errors if e.file.endswith("1.sql")]
    # date_trunc(unknown, bigint) x2, instr(...), "2 days" is no bigint,
    # timestamp + integer
    assert running == ["42883", "42883", "42883", "22P02", "42883"]


@pytest.mark.docker
@pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")
def test_fix_makes_float_and_subtypes_load_and_return_what_oracle_does(tmp_path):
    fixed, _ = fix_double_precision_length(OUTPUT)
    fixed, _ = fix_plsql_integer_subtypes(fixed)
    checks = "DO $$ BEGIN ASSERT gx_l3(2) = 4; ASSERT gx_l4(1) = 6; END $$;\n"  # as in Oracle 23ai
    errors = _load(tmp_path, fixed, checks)
    assert [e for e in errors if e.file.endswith("0.sql")] == []
    assert [e for e in errors if e.file.endswith("1.sql")] == []
