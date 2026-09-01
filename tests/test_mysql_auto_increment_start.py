from ora2pg_gap_report.detectors.mysql_auto_increment_start import (
    find_mysql_auto_increment_start,
)


def test_the_auto_increment_table_option_is_flagged():
    source = (
        "CREATE TABLE invoices (\n"
        "  id INT PRIMARY KEY AUTO_INCREMENT,\n"
        "  amount DECIMAL(10,2)\n"
        ") ENGINE=InnoDB AUTO_INCREMENT=1000 DEFAULT CHARSET=utf8mb4;\n"
    )
    findings = find_mysql_auto_increment_start(source)
    assert len(findings) == 1
    assert findings[0].object_name == "INVOICES"
    assert findings[0].snippet == "AUTO_INCREMENT=1000"
    assert findings[0].severity == "high"
    assert findings[0].line == 4


def test_spacing_around_the_equals_sign_is_tolerated():
    source = "CREATE TABLE t (id INT AUTO_INCREMENT) AUTO_INCREMENT = 42;\n"
    findings = find_mysql_auto_increment_start(source)
    assert [f.snippet for f in findings] == ["AUTO_INCREMENT=42"]


def test_the_column_attribute_alone_is_not_flagged():
    # AUTO_INCREMENT on the column converts correctly (it becomes
    # serial); only the table option carrying the starting value is lost.
    assert find_mysql_auto_increment_start("CREATE TABLE t (id INT AUTO_INCREMENT);\n") == []


def test_an_ordinary_table_is_not_flagged():
    assert find_mysql_auto_increment_start("CREATE TABLE t (id INT PRIMARY KEY);\n") == []
