from ora2pg_gap_report.detectors.mysql_insert_ignore import find_mysql_insert_ignore


def test_insert_ignore_is_flagged():
    source = (
        "CREATE PROCEDURE add_uniq(IN p_id INT)\n"
        "BEGIN\n"
        "  INSERT IGNORE INTO uniq1 (id, v) VALUES (p_id, 1);\n"
        "END;\n"
    )
    findings = find_mysql_insert_ignore(source)
    assert len(findings) == 1
    assert findings[0].object_name == "ADD_UNIQ"
    assert findings[0].snippet == "INSERT IGNORE"
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_a_plain_insert_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN INSERT INTO t (id) VALUES (1); END;\n"
    assert find_mysql_insert_ignore(source) == []


def test_a_column_named_ignore_something_is_not_flagged():
    assert find_mysql_insert_ignore("CREATE TABLE t (ignore_flag INT);\n") == []


def test_the_phrase_inside_a_string_literal_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN SELECT 'INSERT IGNORE'; END;\n"
    assert find_mysql_insert_ignore(source) == []
