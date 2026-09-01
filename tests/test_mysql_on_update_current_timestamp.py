from ora2pg_gap_report.detectors.mysql_on_update_current_timestamp import (
    find_mysql_on_update_current_timestamp,
)


def test_on_update_current_timestamp_is_flagged():
    source = (
        "CREATE TABLE sessions (\n"
        "  id INT PRIMARY KEY AUTO_INCREMENT,\n"
        "  token VARCHAR(64) NOT NULL,\n"
        "  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP\n"
        ");\n"
    )
    findings = find_mysql_on_update_current_timestamp(source)
    assert len(findings) == 1
    assert findings[0].object_name == "SESSIONS"
    assert findings[0].snippet == "ON UPDATE CURRENT_TIMESTAMP"
    assert findings[0].severity == "high"
    assert findings[0].line == 4


def test_a_plain_default_current_timestamp_without_on_update_is_not_flagged():
    source = "CREATE TABLE t (created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);\n"
    assert find_mysql_on_update_current_timestamp(source) == []


def test_an_ordinary_column_list_is_not_flagged():
    assert find_mysql_on_update_current_timestamp("CREATE TABLE t (id INT);\n") == []


def test_the_phrase_inside_a_string_literal_is_not_flagged():
    source = "CREATE TABLE t (note VARCHAR(80) DEFAULT 'ON UPDATE CURRENT_TIMESTAMP');\n"
    assert find_mysql_on_update_current_timestamp(source) == []


def test_a_bare_ctas_with_no_column_list_is_not_flagged():
    assert find_mysql_on_update_current_timestamp("CREATE TABLE t AS SELECT * FROM other;\n") == []
