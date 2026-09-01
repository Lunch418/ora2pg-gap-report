from ora2pg_gap_report.detectors.mysql_enum_type import find_mysql_enum_columns


def test_an_enum_column_is_flagged():
    source = (
        "CREATE TABLE orders (\n"
        "  id INT PRIMARY KEY AUTO_INCREMENT,\n"
        "  status ENUM('new','paid','shipped','cancelled') NOT NULL DEFAULT 'new'\n"
        ");\n"
    )
    findings = find_mysql_enum_columns(source)
    assert len(findings) == 1
    assert findings[0].object_name == "ORDERS"
    assert findings[0].snippet == "ENUM(...)"
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_a_backtick_quoted_table_name_is_read():
    source = "CREATE TABLE `orders` (status ENUM('a','b'));\n"
    findings = find_mysql_enum_columns(source)
    assert findings[0].object_name == "ORDERS"


def test_two_enum_columns_in_the_same_table_are_both_flagged():
    source = "CREATE TABLE t (a ENUM('x','y'), b ENUM('p','q'));\n"
    assert len(find_mysql_enum_columns(source)) == 2


def test_an_ordinary_column_list_is_not_flagged():
    assert find_mysql_enum_columns("CREATE TABLE t (id INT, name VARCHAR(30));\n") == []


def test_a_similarly_named_column_is_not_flagged():
    assert find_mysql_enum_columns("CREATE TABLE t (enum_id INT);\n") == []


def test_a_bare_ctas_with_no_column_list_is_not_flagged():
    assert find_mysql_enum_columns("CREATE TABLE t AS SELECT * FROM other;\n") == []


def test_an_enum_inside_a_string_literal_is_not_flagged():
    source = "CREATE TABLE t (note VARCHAR(50) DEFAULT 'looks like ENUM(x)');\n"
    assert find_mysql_enum_columns(source) == []
