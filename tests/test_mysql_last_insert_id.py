from ora2pg_gap_report.detectors.mysql_last_insert_id import find_mysql_last_insert_id


def test_last_insert_id_is_flagged():
    source = (
        "CREATE PROCEDURE p26()\n"
        "BEGIN\n"
        "  INSERT INTO t26 (v) VALUES (1);\n"
        "  SELECT LAST_INSERT_ID();\n"
        "END;\n"
    )
    findings = find_mysql_last_insert_id(source)
    assert len(findings) == 1
    assert findings[0].object_name == "P26"
    assert findings[0].snippet == "LAST_INSERT_ID()"
    assert findings[0].severity == "high"
    assert findings[0].line == 4


def test_a_procedure_without_it_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN INSERT INTO t (id) VALUES (1); END;\n"
    assert find_mysql_last_insert_id(source) == []


def test_a_similarly_named_column_is_not_flagged():
    assert find_mysql_last_insert_id("CREATE TABLE t (last_insert_id_value INT);\n") == []


def test_the_call_inside_a_string_literal_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN SELECT 'LAST_INSERT_ID()'; END;\n"
    assert find_mysql_last_insert_id(source) == []
