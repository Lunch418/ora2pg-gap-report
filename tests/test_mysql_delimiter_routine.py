import pytest

from ora2pg_gap_report.detectors.mysql_delimiter_routine import find_mysql_delimiter_routines

# Verbatim shape of MySQL 8.0.46's mysqldump --routines output.
MYSQLDUMP_PROCEDURE = (
    "/*!50003 SET sql_mode              = 'STRICT_TRANS_TABLES' */ ;\n"
    "DELIMITER ;;\n"
    "CREATE DEFINER=`root`@`localhost` PROCEDURE `film_in_stock`(IN p_film_id INT, IN p_store_id INT, OUT p_film_count INT)\n"
    "    READS SQL DATA\n"
    "BEGIN\n"
    "     SELECT inventory_id FROM inventory WHERE film_id = p_film_id;\n"
    "END ;;\n"
    "DELIMITER ;\n"
    "/*!50003 SET sql_mode              = @saved_sql_mode */ ;\n"
)


def test_a_mysqldump_procedure_is_flagged():
    findings = find_mysql_delimiter_routines(MYSQLDUMP_PROCEDURE)
    assert [(f.object_name, f.snippet, f.line, f.severity) for f in findings] == [
        ("FILM_IN_STOCK", "DELIMITER ;;", 3, "high")
    ]


@pytest.mark.parametrize("delimiter", ["//", "$$", "|", "$"])
def test_a_function_under_any_other_delimiter_is_flagged(delimiter):
    source = (
        f"DELIMITER {delimiter}\n"
        "CREATE FUNCTION add_one(p INT) RETURNS int DETERMINISTIC\n"
        f"BEGIN\n  RETURN p + 1;\nEND {delimiter}\n"
        "DELIMITER ;\n"
    )
    assert [f.object_name for f in find_mysql_delimiter_routines(source)] == ["ADD_ONE"]


def test_a_routine_without_a_delimiter_directive_is_not_flagged():
    # The same routine, ended with a plain ';': ora2pg converts it and it
    # loads and runs.
    source = "CREATE FUNCTION add_one(p INT) RETURNS int DETERMINISTIC\nBEGIN\n  RETURN p + 1;\nEND;\n"
    assert find_mysql_delimiter_routines(source) == []


def test_a_routine_after_the_delimiter_is_reset_is_not_flagged():
    source = (
        "DELIMITER ;;\nCREATE PROCEDURE a() BEGIN SELECT 1; END ;;\nDELIMITER ;\n"
        "CREATE PROCEDURE b() BEGIN SELECT 2; END;\n"
    )
    assert [f.object_name for f in find_mysql_delimiter_routines(source)] == ["A"]


def test_a_trigger_is_not_this_detectors_business():
    source = "DELIMITER //\nCREATE TRIGGER t_bi BEFORE INSERT ON t FOR EACH ROW BEGIN SET NEW.b = 1; END //\nDELIMITER ;\n"
    assert find_mysql_delimiter_routines(source) == []


def test_a_delimiter_inside_a_comment_or_string_is_not_read():
    source = (
        "-- DELIMITER ;;\n"
        "SELECT 'DELIMITER //';\n"
        "CREATE PROCEDURE p() BEGIN SELECT 1; END;\n"
    )
    assert find_mysql_delimiter_routines(source) == []
