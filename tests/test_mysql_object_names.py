"""MySQL/MariaDB allow ALGORITHM, DEFINER and SQL SECURITY between CREATE
and the object keyword, and mysqldump writes them on every routine and
view: CREATE DEFINER=`root`@`localhost` PROCEDURE ... . The object-name
patterns only allowed OR REPLACE there, so no routine in a real dump was
recognised as an object, and every finding inside one was attributed to
whichever table the dump created last (a LIMIT n, m and a SIGNAL in a
procedure of a real MySQL 8.0.46 mysqldump of sakila came out as table
STORE). IF NOT EXISTS on a routine named it "IF"."""

import pytest

from ora2pg_gap_report import mysql_lex
from ora2pg_gap_report.core import scan_source


def _names(source: str) -> list[str]:
    clean = mysql_lex.mask_strings_and_comments(source)
    return [name for _, kind, name in mysql_lex.enclosing_object_name_index(clean) if kind != "end"]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("CREATE DEFINER=`root`@`localhost` PROCEDURE `gap_probe`(p INT) BEGIN END", "GAP_PROBE"),
        ("CREATE DEFINER='root'@'%' PROCEDURE p() BEGIN END", "P"),
        ("CREATE DEFINER=root@localhost PROCEDURE sch.p() BEGIN END", "P"),
        ("CREATE DEFINER=CURRENT_USER FUNCTION f() RETURNS int RETURN 1", "F"),
        ("CREATE DEFINER=CURRENT_USER() TRIGGER t BEFORE INSERT ON x FOR EACH ROW SET NEW.a = 1", "T"),
        (
            "CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `v` AS select 1",
            "V",
        ),
        ("CREATE OR REPLACE SQL SECURITY INVOKER VIEW v AS select 1", "V"),
        ("CREATE PROCEDURE IF NOT EXISTS p() BEGIN END", "P"),
        ("CREATE OR REPLACE DEFINER=`root`@`%` AGGREGATE FUNCTION agg(x int) RETURNS int SONAME 'a.so'", "AGG"),
    ],
)
def test_an_object_is_named_whatever_comes_between_create_and_its_keyword(source, expected):
    assert _names(source) == [expected]


def test_a_definer_does_not_reach_across_a_statement_to_the_next_object():
    # An EVENT is not an object this lexer tracks. Its DEFINER must not be
    # read as the prefix of the PROCEDURE in the next statement.
    source = (
        "CREATE DEFINER=`u`@`h` EVENT e ON SCHEDULE EVERY 1 DAY DO SELECT 1;\n"
        "CREATE PROCEDURE q() BEGIN END"
    )
    assert _names(source) == ["Q"]


def test_findings_in_a_mysqldump_routine_belong_to_the_routine_not_the_last_table():
    # Verbatim shape of MySQL 8.0.46's mysqldump --routines output.
    source = (
        "CREATE TABLE `store` (\n  `store_id` tinyint unsigned NOT NULL\n) ENGINE=InnoDB;\n"
        "DELIMITER ;;\n"
        "CREATE DEFINER=`root`@`localhost` PROCEDURE `gap_probe`(p INT)\n"
        "BEGIN\n"
        "  SELECT * FROM film LIMIT 1, 2;\n"
        "  IF p < 0 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'neg'; END IF;\n"
        "END ;;\n"
        "DELIMITER ;\n"
    )
    findings = scan_source(source, "mysql")
    assert {"mysql_limit_comma", "mysql_signal"} <= {f.detector for f in findings}
    # Every finding here is inside the procedure -- the routine-level ones
    # this dump also triggers (DELIMITER, DEFINER) included.
    assert {f.object_name for f in findings} == {"GAP_PROBE"}
