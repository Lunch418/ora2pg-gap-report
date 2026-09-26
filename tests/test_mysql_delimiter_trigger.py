import pytest

from ora2pg_gap_report.detectors.mysql_delimiter_trigger import find_mysql_delimiter_triggers


@pytest.mark.parametrize("delimiter", ["//", "$$", "|", "$"])
def test_a_trigger_under_a_delimiter_without_a_semicolon_is_flagged(delimiter):
    source = (
        f"DELIMITER {delimiter}\n"
        "CREATE TRIGGER t_bi BEFORE INSERT ON t FOR EACH ROW\n"
        f"BEGIN\n  SET NEW.b = NEW.a;\nEND {delimiter}\n"
        "DELIMITER ;\n"
    )
    findings = find_mysql_delimiter_triggers(source)
    assert [(f.object_name, f.snippet, f.line) for f in findings] == [("T_BI", f"DELIMITER {delimiter}", 2)]


def test_a_trigger_with_a_definer_is_named_after_itself():
    source = (
        "DELIMITER //\n"
        "CREATE DEFINER=`root`@`localhost` TRIGGER `audit_ins` AFTER INSERT ON `orders` FOR EACH ROW\n"
        "BEGIN INSERT INTO log VALUES (NEW.id); END //\nDELIMITER ;\n"
    )
    assert [f.object_name for f in find_mysql_delimiter_triggers(source)] == ["AUDIT_INS"]


def test_a_trigger_under_mysqldumps_own_double_semicolon_is_not_flagged():
    # ora2pg finds the end of this one, and converts it.
    source = "DELIMITER ;;\nCREATE TRIGGER t_bi BEFORE INSERT ON t FOR EACH ROW\nBEGIN\n  SET NEW.b = NEW.a;\nEND ;;\nDELIMITER ;\n"
    assert find_mysql_delimiter_triggers(source) == []


def test_a_trigger_without_a_delimiter_is_not_flagged():
    source = "CREATE TRIGGER t_bi BEFORE INSERT ON t FOR EACH ROW SET NEW.b = NEW.a;\n"
    assert find_mysql_delimiter_triggers(source) == []
