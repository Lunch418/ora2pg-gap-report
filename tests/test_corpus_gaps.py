"""GAP-143..148: found in --load-check errors no gap explained, on other
people's code (utPLSQL, OraOpenSource Logger, the Alexandria PL/SQL
library, Oracle's sample schemas) -- checked on a live Oracle 23ai, real
ora2pg 25.0 output recorded in tests/fixtures/corpus_gaps/ and, under the
docker marker, PostgreSQL 16, before and after --prepare and --fix."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ora2pg_gap_report.autofix import FIXERS_BY_DIALECT, fix_trim_both_side
from ora2pg_gap_report.core import scan_source
from ora2pg_gap_report.detectors.call_result_member import find_call_result_member
from ora2pg_gap_report.detectors.hash_identifier import find_hash_identifier
from ora2pg_gap_report.detectors.param_after_default import find_param_after_default
from ora2pg_gap_report.detectors.param_default_spacing import find_param_default_spacing
from ora2pg_gap_report.detectors.sequence_without_start import find_sequence_without_start
from ora2pg_gap_report.detectors.trim_leading_trailing import find_trim_leading_trailing
from ora2pg_gap_report.prepare import (
    PREPARERS_BY_DIALECT,
    prepare_oracle_param_default_spacing,
    prepare_oracle_sequence_start,
)

FIXTURES = Path(__file__).parent / "fixtures" / "corpus_gaps"


def _read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


SEQUENCES = _read("oracle_sequences.sql")
FUNCTIONS = _read("oracle_functions.sql")


def _found(detector, source):
    return [(f.object_name, f.line, f.snippet) for f in detector(source)]


def _routine(header, body="NULL;"):
    return f"CREATE OR REPLACE {header} IS\nBEGIN\n  {body}\nEND;\n/\n"


# --- GAP-143: a sequence without START WITH ------------------------------------------


def test_sequence_without_start():
    assert _found(find_sequence_without_start, SEQUENCES) == [
        ("GX_CS1", 1, "CREATE SEQUENCE gx_cs1"),
        ("GX_CS2", 2, "CREATE SEQUENCE gx_cs2"),
    ]


def test_a_comment_between_the_name_and_the_options():
    # utPLSQL puts its licence there.
    source = "create sequence ut_suite_cache_seq\n  /* licence */\ncache 100;\n"
    assert [s for _, _, s in _found(find_sequence_without_start, source)] == ["CREATE SEQUENCE ut_suite_cache_seq"]
    assert prepare_oracle_sequence_start(source) == (
        "create sequence ut_suite_cache_seq START WITH 1\n  /* licence */\ncache 100;\n",
        1,
    )


@pytest.mark.parametrize(
    ("source", "start"),
    [
        ("create sequence s;", "1"),
        ("create sequence s increment by -1;", "-1"),
        ("create sequence s minvalue 10;", "10"),
        ("create sequence s increment by -2 maxvalue 99;", "99"),
    ],
)
def test_prepare_writes_the_start_oracle_implies(source, start):
    fixed, count = prepare_oracle_sequence_start(source)
    assert count == 1 and f"START WITH {start}" in fixed
    assert prepare_oracle_sequence_start(fixed) == (fixed, 0)


def test_a_started_sequence_and_ora2pgs_working_output_are_left_alone():
    assert find_sequence_without_start("CREATE SEQUENCE s START WITH 5;") == []
    assert find_sequence_without_start("CREATE SEQUENCE s INCREMENT 1 START 5 CACHE 20;") == []
    assert find_sequence_without_start("-- CREATE SEQUENCE s;\nx := 'CREATE SEQUENCE t';") == []


# --- GAP-144: a parameter default with := and no space -------------------------------


def test_param_default_spacing():
    assert _found(find_param_default_spacing, FUNCTIONS) == [
        ("GX_C1", 1, "a_c VARCHAR2:= '.'"),
        ("GX_C1", 1, "a_base INTEGER :=0"),
    ]


def test_spacing_elsewhere_is_left_alone():
    source = _routine("FUNCTION f(a NUMBER := 1, b VARCHAR2 DEFAULT ':=') RETURN NUMBER", "x:=1;")
    assert find_param_default_spacing(source) == []
    declared = "CREATE OR REPLACE FUNCTION f RETURN NUMBER IS\n  v NUMBER:=0;\nBEGIN\n  RETURN v;\nEND;\n/\n"
    assert find_param_default_spacing(declared) == []  # loads in PostgreSQL


def test_prepare_puts_the_spaces_in():
    fixed, count = prepare_oracle_param_default_spacing(FUNCTIONS)
    assert count == 2
    assert "a_c VARCHAR2 := '.', a_base INTEGER := 0)" in fixed
    assert prepare_oracle_param_default_spacing(fixed) == (fixed, 0)
    assert find_param_default_spacing(fixed) == []


# --- GAP-145: TRIM(LEADING ... FROM ...) ---------------------------------------------------


def test_trim_leading_trailing():
    assert _found(find_trim_leading_trailing, FUNCTIONS) == [
        ("GX_C1", 3, "TRIM(LEADING ... FROM ...)"),
        ("GX_C1", 3, "TRIM(TRAILING ... FROM ...)"),
    ]
    assert find_trim_leading_trailing(_routine("FUNCTION f(s VARCHAR2) RETURN VARCHAR2", "RETURN trim(both 'x' from s) || trim(s);")) == []


def test_fix_removes_the_extra_both():
    text = "  RETURN trim(both leading a_c from a_item) || trim(both trailing a_c from a_item) || trim(both a from b);"
    assert fix_trim_both_side(text) == (
        "  RETURN trim(leading a_c from a_item) || trim(trailing a_c from a_item) || trim(both a from b);",
        2,
    )


# --- GAP-146: a parameter without a default after one with a default ----------------------


def test_param_after_default():
    assert _found(find_param_after_default, FUNCTIONS) == [("GX_C2", 6, "p_id OUT after a DEFAULT")]


@pytest.mark.parametrize(
    ("header", "flagged"),
    [
        ("PROCEDURE p(a NUMBER DEFAULT 1, b OUT NUMBER)", True),
        ("PROCEDURE p(a NUMBER := 1, b IN OUT NUMBER)", True),
        ("FUNCTION f(a NUMBER DEFAULT 1, b NUMBER) RETURN NUMBER", True),
        ("FUNCTION f(a NUMBER DEFAULT 1, b IN OUT NUMBER) RETURN NUMBER", True),
        ("FUNCTION f(a NUMBER DEFAULT 1, b OUT NUMBER) RETURN NUMBER", False),  # PostgreSQL takes it
        ("PROCEDURE p(b OUT NUMBER, a NUMBER DEFAULT 1)", False),
        ("PROCEDURE p(a NUMBER DEFAULT 1, b NUMBER DEFAULT 2)", False),
    ],
)
def test_param_after_default_follows_postgresql(header, flagged):
    assert bool(find_param_after_default(_routine(header))) is flagged


# --- GAP-147: a name with # --------------------------------------------------------------------


def test_hash_identifier():
    assert _found(find_hash_identifier, FUNCTIONS) == [("GX_C3", 12, "n#count")]  # once per name and object
    assert find_hash_identifier("x := 'a#b'; -- c#d\n") == []
    assert [s for _, _, s in _found(find_hash_identifier, "SELECT COUNT(*) as #_OF_PRODUCTS FROM t;")] == ["#_OF_PRODUCTS"]


# --- GAP-148: a member of a call's result ---------------------------------------------------------


def test_call_result_member():
    assert _found(find_call_result_member, FUNCTIONS) == [("GX_C4", 19, "extract('/a/text()').getstringval")]


def test_a_collection_elements_field_is_left_alone():
    source = (
        "CREATE OR REPLACE FUNCTION f RETURN VARCHAR2 IS\n"
        "  TYPE t_tab IS TABLE OF emp%ROWTYPE;\n  l_emps t_tab;\n"
        "BEGIN\n  RETURN l_emps(1).ename || TREAT(o AS t_sub).name;\nEND;\n/\n"
    )
    assert find_call_result_member(source) == []


def test_all_six_are_wired_into_the_oracle_scan():
    found = {f.detector for f in scan_source(SEQUENCES + FUNCTIONS, dialect="oracle")}
    assert {
        "sequence_without_start",
        "param_default_spacing",
        "trim_leading_trailing",
        "param_after_default",
        "hash_identifier",
        "call_result_member",
    } <= found


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


@pytest.mark.docker
@pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")
def test_each_error_is_tied_to_its_gap(tmp_path):
    errors = _load(tmp_path, _read("ora2pg_SEQUENCE_output.sql"), _read("ora2pg_FUNCTION_output.sql"))
    assert [(e.sqlstate, e.gap_number) for e in errors] == [
        ("42601", "143"),
        ("42601", "143"),
        ("42601", "144"),  # not GAP-145's, though --fix changes the same routine
        ("42P13", "146"),
        ("42601", "147"),
        ("42601", "148"),
    ]


@pytest.mark.docker
@pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")
def test_prepare_and_fix_make_three_load_and_return_what_oracle_does(tmp_path):
    # ora2pg 25.0's output for the source after --prepare, recorded.
    fixed = []
    for name in ("ora2pg_prepared_SEQUENCE_output.sql", "ora2pg_prepared_FUNCTION_output.sql"):
        text = _read(name)
        for fixer in FIXERS_BY_DIALECT["oracle"]:
            text, _ = fixer(text)
        fixed.append(text)
    checks = (
        "DO $$ BEGIN ASSERT nextval('gx_cs1') = 1; ASSERT nextval('gx_cs2') = 1; "
        "ASSERT nextval('gx_cs3') = 5; ASSERT gx_c1('..ab..') = 'ab..|..ab|0'; END $$;\n"
    )  # as in Oracle 23ai
    errors = _load(tmp_path, *fixed, checks)
    assert [e.gap_number for e in errors] == ["146", "147", "148"]  # no fix for these three


def test_the_prepared_sources_are_what_was_converted():
    for name in ("oracle_sequences.sql", "oracle_functions.sql"):
        text = _read(name)
        for preparer in PREPARERS_BY_DIALECT["oracle"]:
            text, _ = preparer(text)
        assert "START WITH" in text or ":= '.'" in text
