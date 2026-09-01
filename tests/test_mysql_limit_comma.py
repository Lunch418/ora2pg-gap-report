from ora2pg_gap_report.detectors.mysql_limit_comma import find_mysql_limit_comma


def test_the_comma_form_of_limit_is_flagged():
    source = (
        "CREATE PROCEDURE page_rows()\n"
        "BEGIN\n"
        "  SELECT val FROM rows2 ORDER BY id LIMIT 10, 20;\n"
        "END;\n"
    )
    findings = find_mysql_limit_comma(source)
    assert len(findings) == 1
    assert findings[0].object_name == "PAGE_ROWS"
    assert findings[0].snippet == "LIMIT n, m"
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_the_same_form_written_with_parameters_is_flagged():
    source = (
        "CREATE PROCEDURE p(IN p_off INT, IN p_cnt INT)\n"
        "BEGIN\n"
        "  SELECT v FROM t LIMIT p_off, p_cnt;\n"
        "END;\n"
    )
    assert len(find_mysql_limit_comma(source)) == 1


def test_a_plain_limit_without_a_comma_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN SELECT v FROM t LIMIT 10; END;\n"
    assert find_mysql_limit_comma(source) == []


def test_limit_offset_the_postgresql_way_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN SELECT v FROM t LIMIT 20 OFFSET 10; END;\n"
    assert find_mysql_limit_comma(source) == []


def test_the_phrase_inside_a_string_literal_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN SELECT 'LIMIT 10, 20'; END;\n"
    assert find_mysql_limit_comma(source) == []
