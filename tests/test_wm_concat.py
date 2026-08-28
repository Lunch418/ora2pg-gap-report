from ora2pg_gap_report.detectors.wm_concat import find_wm_concat


def test_a_wm_concat_call_is_flagged():
    source = "SELECT dept_id, WM_CONCAT(name) AS names FROM employees GROUP BY dept_id;\n"
    findings = find_wm_concat(source)
    assert len(findings) == 1
    assert findings[0].snippet == "WM_CONCAT("
    assert findings[0].severity == "high"


def test_the_qualified_spellings_are_flagged():
    source = "SELECT WMSYS.WM_CONCAT(a), SYS.WM_CONCAT(b) FROM t;\n"
    assert len(find_wm_concat(source)) == 2


def test_lowercase_is_matched():
    assert len(find_wm_concat("select wm_concat(name) from t;\n")) == 1


def test_listagg_is_not_flagged():
    # ora2pg rewrites LISTAGG into string_agg correctly.
    source = "SELECT LISTAGG(name, ',') WITHIN GROUP (ORDER BY name) FROM t;\n"
    assert find_wm_concat(source) == []


def test_a_similarly_named_function_is_not_flagged():
    assert find_wm_concat("SELECT my_wm_concat_helper(a) FROM t;\n") == []


def test_a_commented_out_call_is_not_flagged():
    assert find_wm_concat("-- WM_CONCAT(name)\nSELECT 1 FROM dual;\n") == []
