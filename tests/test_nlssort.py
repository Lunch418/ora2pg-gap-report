from ora2pg_gap_report.detectors.nlssort import find_nlssort


def test_nlssort_in_order_by_is_flagged():
    source = "SELECT name FROM employees\n ORDER BY NLSSORT(name, 'NLS_SORT=GERMAN');\n"
    findings = find_nlssort(source)
    assert len(findings) == 1
    assert findings[0].snippet == "NLSSORT("
    assert findings[0].severity == "high"
    assert findings[0].line == 2


def test_lowercase_and_extra_whitespace_are_matched():
    source = "select name from t order by nlssort (name, 'NLS_SORT=FRENCH');\n"
    assert len(find_nlssort(source)) == 1


def test_the_nls_sort_parameter_name_alone_is_not_flagged():
    # NLS_SORT (the session parameter) is not NLSSORT (the function).
    source = "ALTER SESSION SET NLS_SORT = 'BINARY';\n"
    assert find_nlssort(source) == []


def test_an_ordinary_order_by_is_not_flagged():
    assert find_nlssort("SELECT name FROM employees ORDER BY name;\n") == []


def test_a_commented_out_call_is_not_flagged():
    source = "-- ORDER BY NLSSORT(name, 'NLS_SORT=GERMAN')\nSELECT name FROM t;\n"
    assert find_nlssort(source) == []
