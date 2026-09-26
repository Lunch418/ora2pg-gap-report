from ora2pg_gap_report.detectors.mysql_definer_procedure import find_mysql_definer_procedures


def test_a_mysqldump_procedure_with_a_definer_is_flagged():
    source = (
        "DELIMITER ;;\n"
        "CREATE DEFINER=`root`@`localhost` PROCEDURE `rewards_report`(IN min_monthly_purchases TINYINT UNSIGNED)\n"
        "BEGIN SELECT 1; END ;;\nDELIMITER ;\n"
    )
    findings = find_mysql_definer_procedures(source)
    assert [(f.object_name, f.line, f.severity) for f in findings] == [("REWARDS_REPORT", 2, "high")]


def test_every_spelling_of_the_definer_is_flagged():
    for definer in ("`app`@`%`", "'app'@'%'", "app@localhost", "CURRENT_USER", "CURRENT_USER()"):
        source = f"CREATE DEFINER={definer} PROCEDURE p() BEGIN SELECT 1; END;\n"
        assert [f.object_name for f in find_mysql_definer_procedures(source)] == ["P"], definer


def test_a_procedure_without_a_definer_is_not_flagged():
    assert find_mysql_definer_procedures("CREATE PROCEDURE p() BEGIN SELECT 1; END;\n") == []


def test_a_function_with_a_definer_is_not_flagged():
    # -t FUNCTION's parser handles DEFINER; the function is exported.
    source = "CREATE DEFINER=`root`@`localhost` FUNCTION f() RETURNS int DETERMINISTIC RETURN 1;\n"
    assert find_mysql_definer_procedures(source) == []


def test_a_definer_on_an_earlier_statement_does_not_reach_the_next_procedure():
    source = (
        "CREATE DEFINER=`u`@`h` EVENT e ON SCHEDULE EVERY 1 DAY DO SELECT 1;\n"
        "CREATE PROCEDURE p() BEGIN SELECT 1; END;\n"
    )
    assert find_mysql_definer_procedures(source) == []
