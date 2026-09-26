"""A finding is attributed to the object that contains it, found by looking
back for the most recent CREATE. Nothing used to end an object, so in a
deployment script anything after a routine -- an anonymous block, a data
fix, a one-off query -- was reported as part of whichever routine came
last. Found on OOS-Utils' install script, where an INSERT ALL in an
anonymous data block was reported as OOS_UTIL_WEB.DOWNLOAD_FILE.

Each dialect's scripts mark the end of a unit of work explicitly, and
that is what ends an object now: SQL*Plus's '/' on a line of its own,
T-SQL's GO batch separator, and MySQL's DELIMITER directive, which
mysqldump and hand-written scripts put around every routine and trigger.
What follows it is attributed to nothing (UNKNOWN) until the next
CREATE -- honest, rather than confidently wrong."""

from ora2pg_gap_report.core import count_objects, scan_source


def _attribution(source: str, dialect: str) -> list[tuple[str, str]]:
    return [(f.detector, f.object_name) for f in scan_source(source, dialect)]


def test_an_oracle_anonymous_block_after_slash_is_not_the_previous_routines():
    source = (
        "CREATE OR REPLACE PACKAGE BODY pkg AS\n"
        "  PROCEDURE p IS BEGIN NULL; END p;\n"
        "END pkg;\n"
        "/\n"
        "BEGIN\n"
        "  INSERT ALL INTO t1 VALUES (1) INTO t2 VALUES (2) SELECT * FROM dual;\n"
        "END;\n"
        "/\n"
    )
    assert _attribution(source, "oracle") == [("insert_all", "UNKNOWN")]


def test_an_oracle_finding_before_the_slash_keeps_its_routine():
    source = (
        "CREATE OR REPLACE PACKAGE BODY pkg AS\n"
        "  PROCEDURE p IS\n"
        "  BEGIN\n"
        "    INSERT ALL INTO t1 VALUES (1) INTO t2 VALUES (2) SELECT * FROM dual;\n"
        "  END p;\n"
        "END pkg;\n"
        "/\n"
    )
    assert _attribution(source, "oracle") == [("insert_all", "PKG.P")]


def test_the_next_oracle_object_after_a_slash_is_attributed_normally():
    source = (
        "CREATE OR REPLACE PROCEDURE first_one IS BEGIN NULL; END;\n"
        "/\n"
        "CREATE OR REPLACE PROCEDURE second_one IS\n"
        "BEGIN\n"
        "  INSERT ALL INTO t1 VALUES (1) INTO t2 VALUES (2) SELECT * FROM dual;\n"
        "END;\n"
        "/\n"
    )
    assert _attribution(source, "oracle") == [("insert_all", "SECOND_ONE")]


def test_a_slash_as_division_or_inside_a_line_does_not_end_an_object():
    # Only '/' alone on its line is the SQL*Plus terminator. A division
    # operator, even one that ends up alone on a wrapped line, is part of
    # an expression -- and so is always followed by more of it, on the
    # same line or the next one. Windows line endings are allowed on the
    # terminator line itself.
    source = (
        "CREATE OR REPLACE PROCEDURE p IS\r\n"
        "  x NUMBER := 10 / 2;\r\n"
        "BEGIN\r\n"
        "  INSERT ALL INTO t1 VALUES (x) INTO t2 VALUES (x) SELECT * FROM dual;\r\n"
        "END;\r\n"
        "/\r\n"
        "BEGIN INSERT ALL INTO t1 VALUES (1) INTO t2 VALUES (2) SELECT * FROM dual; END;\r\n"
    )
    assert _attribution(source, "oracle") == [
        ("insert_all", "P"),
        ("insert_all", "UNKNOWN"),
    ]


def test_slashes_do_not_change_the_object_count():
    source = (
        "CREATE OR REPLACE PACKAGE pkg AS PROCEDURE p; END pkg;\n/\n"
        "CREATE OR REPLACE PACKAGE BODY pkg AS PROCEDURE p IS BEGIN NULL; END; END pkg;\n/\n"
        "CREATE OR REPLACE VIEW v AS SELECT 1 x FROM dual;\n/\n"
    )
    assert count_objects(source) == 3


def test_a_tsql_statement_after_go_is_not_the_previous_procedures():
    source = (
        "CREATE PROCEDURE dbo.P @x INT AS\n"
        "BEGIN\n"
        "  SELECT TOP 1 * FROM T;\n"
        "END\n"
        "GO\n"
        "SELECT TOP 5 * FROM T;\n"
        "go 2\n"
    )
    assert _attribution(source, "mssql") == [
        ("mssql_top_clause", "P"),
        ("mssql_top_clause", "UNKNOWN"),
    ]


def test_a_tsql_identifier_named_go_does_not_end_a_batch():
    source = (
        "CREATE PROCEDURE dbo.P @x INT AS\n"
        "BEGIN\n"
        "  SELECT go\n"
        "  FROM T;\n"
        "  SELECT TOP 1 * FROM T;\n"
        "END\n"
    )
    assert _attribution(source, "mssql") == [("mssql_top_clause", "P")]


def test_a_mysql_statement_after_the_delimiter_reset_is_not_the_previous_routines():
    source = (
        "DELIMITER ;;\n"
        "CREATE PROCEDURE p() BEGIN SELECT * FROM t LIMIT 1, 2; END ;;\n"
        "DELIMITER ;\n"
        "SELECT * FROM t LIMIT 3, 4;\n"
    )
    assert _attribution(source, "mysql") == [
        ("mysql_limit_comma", "P"),
        ("mysql_limit_comma", "UNKNOWN"),
    ]
