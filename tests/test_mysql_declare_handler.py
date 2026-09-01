from ora2pg_gap_report.detectors.mysql_declare_handler import find_mysql_declare_handlers


def test_an_exit_handler_is_flagged():
    source = (
        "CREATE PROCEDURE safe_insert(IN p_id INT)\n"
        "BEGIN\n"
        "  DECLARE EXIT HANDLER FOR SQLEXCEPTION\n"
        "    SELECT 'insert failed, ignored';\n"
        "  INSERT INTO h1 (id, v) VALUES (p_id, 1);\n"
        "END;\n"
    )
    findings = find_mysql_declare_handlers(source)
    assert len(findings) == 1
    assert findings[0].object_name == "SAFE_INSERT"
    assert findings[0].snippet == "DECLARE EXIT HANDLER"
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_a_continue_handler_for_not_found_is_flagged():
    source = (
        "CREATE PROCEDURE p(IN p_id INT)\n"
        "BEGIN\n"
        "  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_found = 1;\n"
        "END;\n"
    )
    findings = find_mysql_declare_handlers(source)
    assert len(findings) == 1
    assert findings[0].snippet == "DECLARE CONTINUE HANDLER"


def test_an_ordinary_declare_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN DECLARE v INT DEFAULT 0; END;\n"
    assert find_mysql_declare_handlers(source) == []


def test_a_declared_cursor_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN DECLARE cur CURSOR FOR SELECT v FROM t; END;\n"
    assert find_mysql_declare_handlers(source) == []


def test_the_phrase_inside_a_string_literal_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN SELECT 'DECLARE EXIT HANDLER FOR ...'; END;\n"
    assert find_mysql_declare_handlers(source) == []
