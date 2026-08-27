from ora2pg_gap_report.detectors.sample_clause import find_sample_clauses


def test_sample_clause_is_flagged_in_a_view():
    source = (
        "CREATE OR REPLACE VIEW v_sampled AS\n"
        "SELECT employee_id, last_name\n"
        "FROM employees SAMPLE (10);\n"
    )
    findings = find_sample_clauses(source)
    assert len(findings) == 1
    assert findings[0].object_name == "V_SAMPLED"
    assert findings[0].snippet == "SAMPLE (10)"
    assert findings[0].severity == "high"


def test_sample_block_with_fractional_percent_is_flagged():
    source = "select * from big_table sample block (0.5);\n"
    findings = find_sample_clauses(source)
    assert len(findings) == 1
    assert findings[0].snippet == "SAMPLE BLOCK (0.5)"


def test_a_column_or_table_named_sample_is_not_flagged():
    # `sample` on its own is an entirely ordinary identifier -- only the
    # keyword immediately followed by a parenthesised percentage is the
    # row-sampling clause.
    source = (
        "CREATE TABLE lab_results (sample NUMBER, result VARCHAR2(20));\n"
        "SELECT sample FROM lab_results;\n"
    )
    assert find_sample_clauses(source) == []


def test_a_function_call_named_sample_with_non_numeric_arg_is_not_flagged():
    source = "SELECT sample(col_name) FROM t;\n"
    assert find_sample_clauses(source) == []
