"""GAP-120..123 on PostgreSQL 16: ora2pg 25.0's real output (recorded in
tests/fixtures/gaps_120_123/ from the sources beside it, which compile and
run in Oracle 23ai) fails to load the way each research doc says, and
--load-check ties every error to its gap; written by hand the way each
doc's verdict says, the same output loads and behaves."""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ora2pg_gap_report.autofix import fix_bare_pg_sleep
from ora2pg_gap_report.load_check import parse_target, run_load_check

FIXTURES = Path(__file__).parent / "fixtures" / "gaps_120_123"


def _docker_usable():
    if not sys.platform.startswith("linux") or shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)"),
]


def _read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def _load(tmp_path, *texts):
    files = []
    for i, text in enumerate(texts):
        path = tmp_path / f"{i}.sql"
        path.write_text(text, encoding="utf-8")
        files.append(path)
    return run_load_check(files, parse_target("docker")).errors


def _gaps(errors):
    return [(e.category, e.gap_number, e.message) for e in errors]


TABLE = _read("types_TABLE_output.sql") + "INSERT INTO gx_emp VALUES (1, 100, 'a'), (2, 200, 'b');\n"
OUT_PKG = "CREATE SCHEMA gx_out_pkg;\nCREATE PROCEDURE gx_out_pkg.note(p text) LANGUAGE plpgsql AS $$ BEGIN NULL; END $$;\n"


def test_types_as_ora2pg_writes_them(tmp_path):
    assert _gaps(_load(tmp_path, TABLE, _read("types_PACKAGE_output.sql"))) == [
        ("gap", "120", 'syntax error at or near "%"'),
        ("gap", "120", 'syntax error at or near "%"'),
        ("gap", "120", 'syntax error at or near "%"'),
        ("gap", "121", 'type "emp_rt" does not exist'),
        ("gap", "121", "type t_name does not exist"),
    ]


def test_types_written_by_hand_load_and_behave(tmp_path):
    fixed = _read("types_PACKAGE_output.sql")
    fixed = fixed.replace("gx_emp.emp_id%TYPE", "numeric(6)").replace("gx_emp.salary%TYPE", "numeric(8,2)")
    fixed = fixed.replace("g_name_def%TYPE", "varchar(40)")  # GAP-120
    fixed = re.sub(r"(?<![.\w])(emp_rt|t_sal|t_name)\b", r"gx_rec_pkg.\1", fixed, flags=re.IGNORECASE)  # GAP-121
    fixed = fixed.replace("CREATE TYPE gx_rec_pkg.gx_rec_pkg.", "CREATE TYPE gx_rec_pkg.")
    fixed = fixed.replace("CREATE DOMAIN gx_rec_pkg.gx_rec_pkg.", "CREATE DOMAIN gx_rec_pkg.")
    check = (
        "DO $$ BEGIN ASSERT gx_rec_pkg.top_salary() = 200; "
        "ASSERT gx_rec_pkg.label('x') = '<x>'; END $$;\n"
    )
    assert _load(tmp_path, TABLE, fixed, check) == ()


def test_calls_as_ora2pg_writes_them_and_after_fix(tmp_path):
    output = _read("calls_PACKAGE_output.sql")
    (tmp_path / "before").mkdir()
    assert _gaps(_load(tmp_path / "before", OUT_PKG, output)) == [
        ("fixable", "123", 'syntax error at or near "pg_sleep"'),
        ("gap", "121", "type t_code does not exist"),
        ("gap", "121", 'type "pair_rt" does not exist'),
        ("gap", "121", 'type "num_tt" does not exist'),
    ]
    fixed, count = fix_bare_pg_sleep(output)
    assert count == 1
    (tmp_path / "after").mkdir()
    assert _gaps(_load(tmp_path / "after", OUT_PKG, fixed))[0] == (
        "gap", "122", 'syntax error at or near "DBMS_APPLICATION_INFO"'
    )


def test_supplied_calls_written_by_hand_load(tmp_path):
    body = _read("calls_PACKAGE_output.sql")
    body = body[: body.index("DROP SCHEMA IF EXISTS gx_t_pkg")]
    body, _ = fix_bare_pg_sleep(body)
    # GAP-122's verdict: a PostgreSQL counterpart, or nothing.
    body = re.sub(r"^\s*(?:DBMS_\w+|UTL_FILE|HTP|OWA_UTIL)\.\w+.*;\n", "", body, flags=re.MULTILINE)
    body = body.replace("gx_out_pkg.note('x');", "CALL gx_out_pkg.note('x');")
    assert _load(tmp_path, OUT_PKG, body, "CALL gx_ext_pkg.run_it();\n") == ()
