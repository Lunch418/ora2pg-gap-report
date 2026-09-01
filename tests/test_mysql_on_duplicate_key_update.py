from ora2pg_gap_report.detectors.mysql_on_duplicate_key_update import (
    find_mysql_on_duplicate_key_update,
)


def test_on_duplicate_key_update_inside_a_procedure_is_flagged():
    source = (
        "CREATE PROCEDURE bump(IN p_id INT)\n"
        "BEGIN\n"
        "  INSERT INTO counters (id, hits) VALUES (p_id, 1)\n"
        "    ON DUPLICATE KEY UPDATE hits = hits + 1;\n"
        "END;\n"
    )
    findings = find_mysql_on_duplicate_key_update(source)
    assert len(findings) == 1
    assert findings[0].object_name == "BUMP"
    assert findings[0].snippet == "ON DUPLICATE KEY UPDATE"
    assert findings[0].severity == "high"
    assert findings[0].line == 4


def test_attributes_to_the_nearest_enclosing_procedure():
    source = (
        "CREATE TABLE t1 (id INT);\n"
        "CREATE PROCEDURE upsert_it(IN p_id INT)\n"
        "BEGIN\n"
        "  INSERT INTO t1 (id) VALUES (p_id) ON DUPLICATE KEY UPDATE id = p_id;\n"
        "END;\n"
    )
    findings = find_mysql_on_duplicate_key_update(source)
    assert findings[0].object_name == "UPSERT_IT"


def test_a_plain_insert_without_on_duplicate_key_update_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN INSERT INTO t (id) VALUES (1); END;\n"
    assert find_mysql_on_duplicate_key_update(source) == []


def test_the_phrase_inside_a_string_literal_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN SELECT 'ON DUPLICATE KEY UPDATE'; END;\n"
    assert find_mysql_on_duplicate_key_update(source) == []
