from pathlib import Path

from ora2pg_gap_report.detectors.mssql_go_separator import find_mssql_go_separator
from ora2pg_gap_report.prepare import prepare_mssql_go_separator

FIXTURES = Path(__file__).parent / "fixtures" / "prepare"

SCRIPT = (
    "SET ANSI_NULLS ON\nGO\n"
    "CREATE PROCEDURE add_order @id int\nAS\nBEGIN\n    INSERT INTO orders (id) VALUES (@id); -- GO\nEND\nGO\n"
    "CREATE TABLE t (go_col int);\nGO 2\n"
    "CREATE FUNCTION next_id (@a int) RETURNS int\nAS\nBEGIN\n    RETURN @a + 1;\nEND;\ngo\n"
)


def test_routines_followed_by_go_are_flagged_at_the_go():
    assert [(f.object_name, f.line) for f in find_mssql_go_separator(SCRIPT)] == [("add_order", 8), ("next_id", 16)]


def test_tables_routines_without_go_and_go_in_comments_are_not_flagged():
    source = "CREATE TABLE t (id int)\nGO\nCREATE PROCEDURE p AS\nBEGIN\n  SELECT 1; /* GO */\nEND;\n"
    assert find_mssql_go_separator(source) == []


def test_ora2pgs_output_with_the_go_inside_is_flagged_and_the_prepared_one_is_not():
    broken = "CREATE OR REPLACE PROCEDURE p (p_id integer) AS $body$\nBEGIN\nBEGIN\n  NULL;\nEND\nGO\nEND;\n$body$\nLANGUAGE PLPGSQL;\n"
    assert [f.line for f in find_mssql_go_separator(broken)] == [6]
    assert find_mssql_go_separator((FIXTURES / "g126_go_separator.sql").read_text(encoding="utf-8")) == []


def test_prepare_drops_go_lines_and_closes_a_bare_end():
    out, count = prepare_mssql_go_separator(SCRIPT)
    assert count == 4
    assert "\nGO" not in out and "\ngo\n" not in out
    assert "END;\nCREATE TABLE t (go_col int);\n" in out  # the bare END got its ;
    assert "-- GO" in out and "go_col" in out  # comments and names untouched
    assert "RETURN @a + 1;\nEND;\n" in out and "END;;" not in out
    assert prepare_mssql_go_separator(out) == (out, 0)
