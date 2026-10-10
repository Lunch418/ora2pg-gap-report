"""GAP-129: an empty string literal where Oracle reads it as NULL, on the
source checked against a live Oracle 23ai and the real ora2pg 25.0 output
recorded in tests/fixtures/empty_string_null/ -- and, under the docker
marker, how PostgreSQL 16 runs that output."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ora2pg_gap_report.detectors.empty_string_null import find_empty_string_null

FIXTURES = Path(__file__).parent / "fixtures" / "empty_string_null"


def _read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def _found(source):
    return [(f.object_name, f.line, f.snippet) for f in find_empty_string_null(source)]


def test_the_checked_source():
    assert _found(_read("oracle_source.sql")) == [
        ("GX_E2", 9, "= ''"),
        ("GX_E5", 24, ":= ''"),
        ("UNKNOWN", 30, "DEFAULT ''"),
        ("GX_E6", 33, "NVL(..., '')"),
    ]


def test_shapes_reported():
    source = (
        "CREATE OR REPLACE PROCEDURE p(a VARCHAR2 DEFAULT '') IS\n"
        "BEGIN\n"
        "  IF a <> '' OR a != '' OR a ^= '' OR '' = a THEN NULL; END IF;\n"
        "  c := COALESCE(a, b, '');\n"
        "  d := NVL(TRIM(a), '');\n"
        "END;\n/\n"
    )
    assert _found(source) == [
        ("P", 1, "DEFAULT ''"),
        ("P", 3, "= ''"),
        ("P", 3, "= ''"),
        ("P", 3, "= ''"),
        ("P", 3, "'' ="),
        ("P", 4, "COALESCE(..., '')"),
        ("P", 5, "NVL(..., '')"),
    ]


def test_ordinary_uses_of_empty_strings_are_left_alone():
    source = (
        "CREATE OR REPLACE PROCEDURE p IS\n"
        "  v VARCHAR2(10) := 'it''s';\n"
        "  w VARCHAR2(10);\n"
        "BEGIN\n"
        "  -- IF w = '' THEN\n"
        "  /* w := ''; */\n"
        "  w := 'a' || '';\n"
        "  w := 'x = '''' here';\n"
        "  w := REPLACE(w, ' ', '');\n"
        "  IF w >= '' THEN NULL; END IF;\n"
        "  DBMS_OUTPUT.PUT_LINE('');\n"
        "  f(p => '');\n"
        "END;\n/\n"
    )
    assert _found(source) == []


def test_ora2pg_copies_them_and_rewrites_nvl_as_coalesce():
    # The same detector over ora2pg's output finds all four again: that is
    # what --verify relies on.
    assert [snippet for _, _, snippet in _found(_read("ora2pg_output.sql"))] == [
        "= ''",
        ":= ''",
        "DEFAULT ''",
        "COALESCE(..., '')",
    ]


# --- PostgreSQL 16 ----------------------------------------------------------


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


SETUP = "INSERT INTO gx_notes (id) VALUES (1);\n"
# What Oracle 23ai returned for the same calls.
AS_IN_ORACLE = _asserts(
    "gx_e2('') = 'other'",
    "gx_e5('x') = 'v is null'",
    "(SELECT count(*) FROM gx_notes WHERE note IS NULL) = 1",
    "gx_e6(NULL) IS NULL",
)
# What PostgreSQL 16 returns.
AS_IN_POSTGRESQL = _asserts(
    "gx_e2('') = 'empty'",
    "gx_e5('x') = 'v is not null'",
    "(SELECT count(*) FROM gx_notes WHERE note = '') = 1",
    "gx_e6(NULL) = ''",
)


@pytest.mark.docker
@pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")
def test_the_output_loads_and_then_behaves_differently(tmp_path):
    output = _read("ora2pg_output.sql")
    (tmp_path / "oracle").mkdir()
    errors = _load(tmp_path / "oracle", output, SETUP, AS_IN_ORACLE)
    assert [e.sqlstate for e in errors] == ["P0004"] * 4  # every one differs, none fails to load
    (tmp_path / "postgresql").mkdir()
    assert _load(tmp_path / "postgresql", output, SETUP, AS_IN_POSTGRESQL) == ()


def test_an_assignment_counts_only_where_the_name_is_tested_for_null():
    reset = (
        "CREATE OR REPLACE PROCEDURE p IS\n  v VARCHAR2(100);\nBEGIN\n"
        "  v := '';\n  v := v || 'x';\nEND;\n/\n"
    )
    assert _found(reset) == []  # NULL || 'x' and '' || 'x' are both 'x'
    tested = reset.replace("  v := v || 'x';\n", "  IF v IS NULL THEN NULL; END IF;\n")
    assert [s for _, _, s in _found(tested)] == [":= ''"]
    default = "CREATE OR REPLACE PROCEDURE p(a VARCHAR2 DEFAULT '') IS\nBEGIN\n  NULL;\nEND;\n/\n"
    assert _found(default) == []
    assert _found(default.replace("  NULL;", "  x := NVL(a, 'none');"))
    assert _found("CREATE TABLE t (note VARCHAR2(20) DEFAULT '');\n")  # a column: always
