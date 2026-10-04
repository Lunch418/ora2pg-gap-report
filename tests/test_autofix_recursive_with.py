import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ora2pg_gap_report.autofix import FIXERS_BY_DIALECT, fix_recursive_with_keyword

FIXTURE = Path(__file__).parent / "fixtures" / "ora2pg_generated_recursive_with_view.sql"


def test_adds_recursive_to_ora2pgs_real_output():
    # Real ora2pg 25.0 output (-t VIEW) for an Oracle recursive WITH.
    source = FIXTURE.read_text(encoding="utf-8")
    fixed, count = fix_recursive_with_keyword(source)
    assert count == 1
    assert "AS WITH RECURSIVE tree(employee_id, manager_id, lvl) AS (" in fixed
    assert fix_recursive_with_keyword(fixed) == (fixed, 0)  # idempotent


def test_a_later_recursive_cte_in_the_list_still_needs_the_keyword_once():
    source = (
        "WITH seed AS (SELECT 1 AS n),\n"
        "     walk (n) AS (SELECT n FROM seed UNION ALL SELECT n + 1 FROM walk WHERE n < 3)\n"
        "SELECT * FROM walk;"
    )
    fixed, count = fix_recursive_with_keyword(source)
    assert count == 1
    assert fixed.startswith("WITH RECURSIVE seed AS")


def test_leaves_non_recursive_with_alone():
    for source in (
        "WITH a AS (SELECT 1) SELECT * FROM a;",
        "WITH a AS (SELECT 1 UNION ALL SELECT 2) SELECT * FROM a;",
        "WITH RECURSIVE t (n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM t WHERE n < 3) SELECT * FROM t;",
    ):
        assert fix_recursive_with_keyword(source) == (source, 0)


def test_skips_oracle_search_and_cycle_clauses():
    source = (
        "WITH t (n) AS (SELECT 1 FROM dual UNION ALL SELECT n + 1 FROM t WHERE n < 3)\n"
        "  CYCLE n SET is_cycle TO 'Y' DEFAULT 'N'\n"
        "SELECT * FROM t;"
    )
    assert fix_recursive_with_keyword(source) == (source, 0)


def test_ignores_text_in_comments_and_strings():
    source = (
        "-- WITH t AS (SELECT 1 UNION ALL SELECT 1 FROM t)\n"
        "SELECT 'WITH t AS (SELECT 1 UNION ALL SELECT 1 FROM t)';"
    )
    assert fix_recursive_with_keyword(source) == (source, 0)


def test_is_registered_for_oracle_only():
    assert fix_recursive_with_keyword in FIXERS_BY_DIALECT["oracle"]
    assert fix_recursive_with_keyword not in FIXERS_BY_DIALECT["mysql"]


def _docker_usable():
    if not sys.platform.startswith("linux") or shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@pytest.mark.docker
@pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")
def test_the_fixed_view_loads_and_walks_the_tree(tmp_path):
    """The method every fix here follows: ora2pg's output fails to load into
    PostgreSQL 16, the fixed output loads and does what the Oracle view did."""
    from ora2pg_gap_report.load_check import parse_target, run_load_check

    table = tmp_path / "0_table.sql"
    table.write_text(
        "CREATE TABLE employees (employee_id integer, manager_id integer);\n"
        "INSERT INTO employees VALUES (1, NULL), (2, 1), (3, 2);\n",
        encoding="utf-8",
    )
    broken = tmp_path / "1_view.sql"
    broken.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    result = run_load_check([table, broken], parse_target("docker"))
    assert [(e.sqlstate, e.gap_number) for e in result.errors] == [("42P01", "024")]

    fixed_text, _ = fix_recursive_with_keyword(FIXTURE.read_text(encoding="utf-8"))
    fixed = tmp_path / "1_view.sql"
    fixed.write_text(
        fixed_text + "\nDO $$ BEGIN ASSERT (SELECT max(lvl) FROM emp_tree) = 3; END $$;\n",
        encoding="utf-8",
    )
    result = run_load_check([table, fixed], parse_target("docker"))
    assert result.errors == ()
