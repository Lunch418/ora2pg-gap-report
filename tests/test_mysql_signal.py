from ora2pg_gap_report.detectors.mysql_signal import find_mysql_signal_statements


def test_signal_inside_a_procedure_is_flagged():
    source = (
        "CREATE PROCEDURE withdraw(IN p_id INT, IN p_amount DECIMAL(12,2))\n"
        "BEGIN\n"
        "  IF p_amount > 100 THEN\n"
        "    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'insufficient funds';\n"
        "  END IF;\n"
        "END;\n"
    )
    findings = find_mysql_signal_statements(source)
    assert len(findings) == 1
    assert findings[0].object_name == "WITHDRAW"
    assert findings[0].snippet == "SIGNAL"
    assert findings[0].severity == "high"
    assert findings[0].line == 4


def test_resignal_is_also_flagged():
    source = (
        "CREATE PROCEDURE p()\n"
        "BEGIN\n"
        "  DECLARE CONTINUE HANDLER FOR SQLEXCEPTION RESIGNAL;\n"
        "END;\n"
    )
    findings = find_mysql_signal_statements(source)
    assert len(findings) == 1
    assert findings[0].snippet == "RESIGNAL"


def test_attributes_to_the_nearest_enclosing_procedure():
    source = (
        "CREATE TABLE t1 (id INT);\n"
        "CREATE PROCEDURE guard_it()\n"
        "BEGIN\n"
        "  SIGNAL SQLSTATE '45000';\n"
        "END;\n"
    )
    findings = find_mysql_signal_statements(source)
    assert findings[0].object_name == "GUARD_IT"


def test_a_procedure_without_signal_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN SELECT 1; END;\n"
    assert find_mysql_signal_statements(source) == []


def test_the_word_inside_a_string_literal_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN SELECT 'please SIGNAL support'; END;\n"
    assert find_mysql_signal_statements(source) == []
