from ora2pg_gap_report.detectors.mysql_versioned_comment import find_mysql_versioned_comments


def test_a_mysqldump_trigger_is_flagged():
    # Verbatim shape of MySQL 8.0.46's mysqldump --triggers output.
    source = (
        "DELIMITER ;;\n"
        "/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `customer_create_date` "
        "BEFORE INSERT ON `customer` FOR EACH ROW SET NEW.create_date = NOW() */;;\n"
        "DELIMITER ;\n"
    )
    findings = find_mysql_versioned_comments(source)
    assert [(f.object_name, f.snippet, f.line) for f in findings] == [
        ("CUSTOMER_CREATE_DATE", "/*!... CREATE TRIGGER ... */", 2)
    ]


def test_a_mysqldump_view_is_flagged():
    source = (
        "/*!50001 DROP VIEW IF EXISTS `actor_info`*/;\n"
        "/*!50001 CREATE ALGORITHM=UNDEFINED */\n"
        "/*!50013 DEFINER=`root`@`localhost` SQL SECURITY INVOKER */\n"
        "/*!50001 VIEW `actor_info` AS select 1 AS `x` */;\n"
    )
    assert [(f.object_name, f.line) for f in find_mysql_versioned_comments(source)] == [("ACTOR_INFO", 2)]


def test_an_old_mysqldump_routine_is_flagged():
    source = (
        "/*!50003 CREATE*/ /*!50020 DEFINER=`root`@`localhost`*/ /*!50003 PROCEDURE `bump`(p INT)\n"
        "BEGIN\n  UPDATE t SET a = a + p;\nEND */;;\n"
    )
    assert [f.object_name for f in find_mysql_versioned_comments(source)] == ["BUMP"]


def test_mysqldumps_session_settings_are_not_flagged():
    source = (
        "/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;\n"
        "/*!50003 SET sql_mode = @saved_sql_mode */ ;\n"
        "/*!50001 DROP VIEW IF EXISTS `actor_info`*/;\n"
        "/*!40000 ALTER TABLE `actor` DISABLE KEYS */;\n"
    )
    assert find_mysql_versioned_comments(source) == []


def test_a_plain_create_and_a_string_that_looks_like_one_are_not_flagged():
    source = (
        "CREATE TRIGGER t_bi BEFORE INSERT ON t FOR EACH ROW SET NEW.b = 1;\n"
        "INSERT INTO docs VALUES ('/*!50003 CREATE*/ /*!50003 TRIGGER x */');\n"
    )
    assert find_mysql_versioned_comments(source) == []
