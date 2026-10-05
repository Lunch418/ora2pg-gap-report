import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ora2pg_gap_report.autofix import fix_mysql_limit_comma

FIXTURE = Path(__file__).parent / "fixtures" / "ora2pg_generated_mysql_limit_comma.sql"


def test_rewrites_ora2pgs_real_output():
    # Real ora2pg 25.0 -m -t PROCEDURE output for MySQL's LIMIT a, b.
    fixed, count = fix_mysql_limit_comma(FIXTURE.read_text(encoding="utf-8"))
    assert count == 2
    assert "ORDER BY id LIMIT 20 OFFSET 10;" in fixed
    assert "ORDER BY id LIMIT p_count OFFSET p_offset;" in fixed
    assert fix_mysql_limit_comma(fixed) == (fixed, 0)  # idempotent


def test_keeps_the_keyword_spelling_and_spacing():
    assert fix_mysql_limit_comma("select 1 limit  5,10;") == ("select 1 limit  10 OFFSET 5;", 1)


def test_leaves_valid_and_unclear_shapes_alone():
    for source in (
        "SELECT 1 LIMIT 5 OFFSET 10;",              # already PostgreSQL
        "SELECT 1 LIMIT 5;",
        "SELECT 'LIMIT 1, 2';",                     # inside a string
        "SELECT 1; -- LIMIT 1, 2",                  # inside a comment
        'SELECT "LIMIT 1, 2" FROM t;',              # a quoted identifier
        "SELECT 1 LIMIT a, b + 1;",                 # an expression: not MySQL's shape
        "SELECT 1 LIMIT f(1), 2;",
    ):
        assert fix_mysql_limit_comma(source) == (source, 0), source


def _docker_usable():
    if not sys.platform.startswith("linux") or shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@pytest.mark.docker
@pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")
def test_the_broken_output_fails_and_the_fixed_one_loads(tmp_path):
    from ora2pg_gap_report.load_check import parse_target, run_load_check

    table = tmp_path / "0_table.sql"
    table.write_text("CREATE TABLE rows2 (id integer, val text);\n", encoding="utf-8")
    routine = tmp_path / "1_proc.sql"
    routine.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    broken = run_load_check([table, routine], parse_target("docker"), dialect="mysql")
    assert [(e.sqlstate, e.category, e.gap_number) for e in broken.errors] == [("42601", "fixable", "075")]

    fixed_text, _ = fix_mysql_limit_comma(FIXTURE.read_text(encoding="utf-8"))
    routine.write_text(
        fixed_text
        + "\nINSERT INTO rows2 SELECT g, 'v' || g FROM generate_series(1, 40) AS g;\n"
        + "DO $$ BEGIN ASSERT (SELECT array_agg(id) FROM (SELECT id FROM rows2 ORDER BY id LIMIT 3 OFFSET 10) s)"
        + " = ARRAY[11, 12, 13]; END $$;\n",
        encoding="utf-8",
    )
    assert run_load_check([table, routine], parse_target("docker"), dialect="mysql").errors == ()
