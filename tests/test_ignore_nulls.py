from ora2pg_gap_report.detectors.ignore_nulls import find_ignore_nulls


def test_ignore_nulls_on_an_analytic_function_is_flagged():
    source = (
        "SELECT emp_id,\n"
        "       LAST_VALUE(salary IGNORE NULLS) OVER (ORDER BY hired) AS last_sal\n"
        "  FROM employees;\n"
    )
    findings = find_ignore_nulls(source)
    assert len(findings) == 1
    assert findings[0].snippet == "IGNORE NULLS"
    assert findings[0].severity == "high"
    assert findings[0].line == 2


def test_respect_nulls_is_flagged_too():
    # Oracle's default, but legal to spell out -- and ora2pg copies it
    # through exactly like IGNORE NULLS (confirmed by its own probe).
    source = "SELECT FIRST_VALUE(salary RESPECT NULLS) OVER (ORDER BY hired) FROM employees;\n"
    findings = find_ignore_nulls(source)
    assert len(findings) == 1
    assert findings[0].snippet == "RESPECT NULLS"


def test_both_forms_in_one_statement_are_reported_separately():
    source = (
        "SELECT LAST_VALUE(a IGNORE NULLS) OVER (), \n"
        "       LAG(b) IGNORE NULLS OVER ()\n"
        "  FROM t;\n"
    )
    assert len(find_ignore_nulls(source)) == 2


def test_an_ordinary_analytic_function_is_not_flagged():
    source = "SELECT LAG(bonus, 1) OVER (ORDER BY hired) FROM employees;\n"
    assert find_ignore_nulls(source) == []


def test_the_words_inside_a_comment_are_not_flagged():
    source = "-- LAST_VALUE(x IGNORE NULLS) was removed here\nSELECT 1 FROM dual;\n"
    assert find_ignore_nulls(source) == []


def test_the_words_inside_a_string_literal_are_not_flagged():
    source = "SELECT 'IGNORE NULLS' AS note FROM dual;\n"
    assert find_ignore_nulls(source) == []


def test_the_enclosing_routine_is_attributed():
    source = (
        "CREATE OR REPLACE PROCEDURE report_gaps IS\n"
        "BEGIN\n"
        "  SELECT LAST_VALUE(v IGNORE NULLS) OVER () INTO x FROM t;\n"
        "END;\n"
    )
    findings = find_ignore_nulls(source)
    assert len(findings) == 1
    assert findings[0].object_name == "REPORT_GAPS"
