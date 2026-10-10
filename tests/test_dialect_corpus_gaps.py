"""GAP-149..152: SQL Server and MySQL, found running --migrate --load-check
on jOOQ's Sakila, the Employees database and Microsoft's sample databases
-- on real ora2pg 25.0 output recorded in
tests/fixtures/dialect_corpus_gaps/ (before and after --prepare) and,
under the docker marker, PostgreSQL 16."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ora2pg_gap_report.autofix import FIXERS_BY_DIALECT, fix_mssql_with_rollup, fix_mysql_with_rollup
from ora2pg_gap_report.core import scan_source
from ora2pg_gap_report.detectors.mssql_index_name_collision import find_mssql_index_name_collision
from ora2pg_gap_report.detectors.mssql_statement_terminator import find_mssql_statement_terminator
from ora2pg_gap_report.detectors.mssql_with_rollup import find_mssql_with_rollup
from ora2pg_gap_report.detectors.mysql_with_rollup import find_mysql_with_rollup
from ora2pg_gap_report.prepare import prepare_mssql_go_separator, prepare_mssql_index_names

FIXTURES = Path(__file__).parent / "fixtures" / "dialect_corpus_gaps"


def _read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


MSSQL = _read("mssql_source.sql")
MYSQL = _read("mysql_source.sql")


def _found(detector, source):
    return [(f.object_name, f.line, f.snippet) for f in detector(source)]


# --- GAP-149: statements without ; ------------------------------------------------------


def test_statement_terminator_once_per_file():
    assert _found(find_mssql_statement_terminator, MSSQL) == [
        ("UNKNOWN", 1, "CREATE TABLE store ( (no ; at its end, 6 statements)")
    ]


def test_ora2pg_drops_what_follows_and_prepare_brings_it_back():
    # ora2pg 25.0 -M on the source as it is: one table of three.
    assert _read("mssql_TABLE_output.sql").count("CREATE TABLE") == 1
    assert _read("mssql_prepared_TABLE_output.sql").count("CREATE TABLE") == 3


def test_prepare_ends_every_statement():
    fixed, _ = prepare_mssql_go_separator(MSSQL)
    assert "GO" not in fixed
    assert find_mssql_statement_terminator(fixed) == []
    # Sakila's film_text: neither ; nor GO before the next CREATE TABLE.
    assert ")\n;" not in fixed and "  PRIMARY KEY NONCLUSTERED (staff_id),\n);" in fixed


def test_terminated_statements_and_routines_are_not_flagged():
    assert find_mssql_statement_terminator("CREATE TABLE a (x INT);\nGO\nCREATE TABLE b (y INT);\n") == []
    # A routine's GO is GAP-126's.
    assert find_mssql_statement_terminator("CREATE PROCEDURE p AS\nBEGIN\n  SELECT 1;\nEND\nGO\n") == []


# --- GAP-150: one index name on several tables --------------------------------------------


def test_index_name_collision():
    assert _found(find_mssql_index_name_collision, MSSQL) == [
        ("STAFF", 22, "idx_fk_store_id"),
        ("CUSTOMER", 24, "idx_fk_store_id"),
    ]


def test_prepare_renames_the_later_ones():
    fixed, count = prepare_mssql_index_names(MSSQL)
    assert count == 2
    assert "INDEX idx_fk_store_id ON store" in fixed
    assert "INDEX staff_idx_fk_store_id ON staff" in fixed and "INDEX customer_idx_fk_store_id ON customer" in fixed
    assert prepare_mssql_index_names(fixed) == (fixed, 0)
    bracketed = "CREATE INDEX [ix] ON t1(a);\nCREATE NONCLUSTERED INDEX [ix] ON [dbo].[t2](a);\n"
    assert "[t2_ix]" in prepare_mssql_index_names(bracketed)[0]


# --- GAP-151, GAP-152: GROUP BY ... WITH ROLLUP -----------------------------------------------


def test_with_rollup_in_both_dialects():
    assert _found(find_mssql_with_rollup, MSSQL) == [("STAFF_TOTALS", 28, "GROUP BY ... WITH ROLLUP")]
    assert [s for _, _, s in _found(find_mysql_with_rollup, MYSQL)] == ["GROUP BY ... WITH ROLLUP"]
    assert find_mssql_with_rollup("SELECT a FROM t GROUP BY a; -- GROUP BY a WITH ROLLUP\n") == []


@pytest.mark.parametrize("fixer", [fix_mssql_with_rollup, fix_mysql_with_rollup])
def test_fix_writes_rollup(fixer):
    text = "  SELECT store_id, SUM(amount) FROM staff GROUP BY store_id, x WITH ROLLUP;\n  x := 'WITH ROLLUP';"
    assert fixer(text) == (
        "  SELECT store_id, SUM(amount) FROM staff GROUP BY ROLLUP (store_id, x);\n  x := 'WITH ROLLUP';",
        1,
    )
    assert fixer("SELECT a FROM t GROUP BY a WITH CUBE")[0] == "SELECT a FROM t GROUP BY CUBE (a)"


def test_all_four_are_wired_into_their_dialects():
    assert {"mssql_statement_terminator", "mssql_index_name_collision", "mssql_with_rollup"} <= {
        f.detector for f in scan_source(MSSQL, dialect="mssql")
    }
    assert "mysql_with_rollup" in {f.detector for f in scan_source(MYSQL, dialect="mysql")}


# --- PostgreSQL 16 -------------------------------------------------------------


def _docker_usable():
    if not sys.platform.startswith("linux") or shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _load(tmp_path, *texts, dialect):
    from ora2pg_gap_report.load_check import parse_target, run_load_check

    files = []
    for i, text in enumerate(texts):
        path = tmp_path / f"{i}.sql"
        path.write_text(text, encoding="utf-8")
        files.append(path)
    return run_load_check(files, parse_target("docker"), dialect=dialect).errors


ROLLUP_CHECK = (
    "INSERT INTO {table} (store_id, amount) VALUES (1, 10), (1, 5), (2, 7);\n"
    "DO $$ BEGIN ASSERT (SELECT array_agg(total ORDER BY store_id NULLS LAST) FROM {view}) = ARRAY[15, 7, 22]::bigint[]; END $$;\n"
)


@pytest.mark.docker
@pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")
def test_mssql_before_and_after(tmp_path):
    (tmp_path / "before").mkdir()
    before = _load(tmp_path / "before", _read("mssql_TABLE_output.sql"), _read("mssql_PROCEDURE_output.sql"), dialect="mssql")
    assert [(e.sqlstate, e.gap_number) for e in before] == [("42601", "151")]  # staff and customer are not even there
    fixed = []
    for name in ("mssql_prepared_TABLE_output.sql", "mssql_prepared_PROCEDURE_output.sql"):
        text = _read(name)
        for fixer in FIXERS_BY_DIALECT["mssql"]:
            text, _ = fixer(text)
        fixed.append(text)
    check = (
        "INSERT INTO staff VALUES (1, 1, 10), (2, 1, 5), (3, 2, 7);\n"
        "DO $$ BEGIN ASSERT (SELECT count(*) FROM customer) = 0; END $$;\n"
    )
    (tmp_path / "after").mkdir()
    assert _load(tmp_path / "after", *fixed, check, dialect="mssql") == ()


@pytest.mark.docker
@pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")
def test_mysql_rollup_before_and_after(tmp_path):
    table, view = _read("mysql_TABLE_output.sql"), _read("mysql_VIEW_output.sql")
    (tmp_path / "before").mkdir()
    before = _load(tmp_path / "before", table, view, dialect="mysql")
    assert [(e.sqlstate, e.gap_number) for e in before] == [("42601", "152")]
    fixed, _ = fix_mysql_with_rollup(view)
    (tmp_path / "after").mkdir()
    check = ROLLUP_CHECK.format(table="payment", view="payment_totals")
    assert _load(tmp_path / "after", table, fixed, check, dialect="mysql") == ()
