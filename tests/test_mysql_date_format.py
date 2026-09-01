from ora2pg_gap_report.detectors.mysql_date_format import find_mysql_date_format


def test_date_format_is_flagged():
    source = (
        "CREATE PROCEDURE p22()\n"
        "BEGIN\n"
        "  SELECT DATE_FORMAT(d, '%Y-%m-%d %H:%i:%s') FROM t22;\n"
        "END;\n"
    )
    findings = find_mysql_date_format(source)
    assert len(findings) == 1
    assert findings[0].object_name == "P22"
    assert findings[0].snippet == "DATE_FORMAT(...)"
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_spacing_before_the_paren_is_tolerated():
    source = "CREATE PROCEDURE p() BEGIN SELECT DATE_FORMAT (d, '%Y') FROM t; END;\n"
    assert len(find_mysql_date_format(source)) == 1


def test_a_procedure_without_it_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN SELECT to_char(d, 'YYYY') FROM t; END;\n"
    assert find_mysql_date_format(source) == []


def test_a_similarly_named_column_is_not_flagged():
    assert find_mysql_date_format("CREATE TABLE t (date_format_id INT);\n") == []


def test_the_call_inside_a_string_literal_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN SELECT 'DATE_FORMAT(d, x)'; END;\n"
    assert find_mysql_date_format(source) == []
