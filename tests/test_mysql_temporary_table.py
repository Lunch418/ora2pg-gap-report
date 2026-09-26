from ora2pg_gap_report.detectors.mysql_temporary_table import find_mysql_temporary_tables


def test_a_top_level_temporary_table_is_flagged():
    source = "CREATE TEMPORARY TABLE `cart_tmp` (\n  `session_id` int NOT NULL\n) ENGINE=InnoDB;\n"
    findings = find_mysql_temporary_tables(source)
    assert [(f.object_name, f.line, f.snippet) for f in findings] == [("CART_TMP", 1, "CREATE TEMPORARY TABLE")]


def test_a_temporary_table_after_a_routine_has_ended_is_flagged():
    source = (
        "DELIMITER ;;\nCREATE PROCEDURE p() BEGIN SELECT 1; END ;;\nDELIMITER ;\n"
        "CREATE TEMPORARY TABLE staging (id int);\n"
    )
    assert [f.object_name for f in find_mysql_temporary_tables(source)] == ["STAGING"]


def test_a_temporary_table_inside_a_procedure_is_not_flagged():
    # Copied into the PL/pgSQL body as written: still temporary there.
    source = (
        "DELIMITER ;;\n"
        "CREATE PROCEDURE p()\nBEGIN\n  CREATE TEMPORARY TABLE staging (id int);\nEND ;;\n"
        "DELIMITER ;\n"
    )
    assert find_mysql_temporary_tables(source) == []


def test_temporary_with_if_not_exists_is_left_to_that_gap():
    # There ora2pg keeps TEMPORARY and mangles the table instead (GAP-110).
    assert find_mysql_temporary_tables("CREATE TEMPORARY TABLE IF NOT EXISTS t (id int);\n") == []


def test_a_plain_table_is_not_flagged():
    assert find_mysql_temporary_tables("CREATE TABLE t (id int);\n") == []
