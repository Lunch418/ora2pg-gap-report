from ora2pg_gap_report.detectors.keep_dense_rank import find_keep_dense_rank


def test_keep_dense_rank_first_and_last_are_both_flagged():
    source = (
        "CREATE OR REPLACE VIEW v_dept_top AS\n"
        "SELECT department_id,\n"
        "       MAX(salary) KEEP (DENSE_RANK FIRST ORDER BY hire_date) AS first_sal,\n"
        "       MIN(salary) KEEP (DENSE_RANK LAST ORDER BY hire_date) AS last_sal\n"
        "FROM employees\n"
        "GROUP BY department_id;\n"
    )
    findings = find_keep_dense_rank(source)
    assert len(findings) == 2
    assert all(f.object_name == "V_DEPT_TOP" for f in findings)
    assert all(f.snippet == "KEEP (DENSE_RANK ...)" for f in findings)
    assert all(f.severity == "high" for f in findings)


def test_keep_dense_rank_is_flagged_inside_a_procedure():
    source = (
        "create or replace procedure report_top is\n"
        "begin\n"
        "  select max(sal) keep (dense_rank first order by hd) into v from emp;\n"
        "end;\n"
        "/\n"
    )
    findings = find_keep_dense_rank(source)
    assert len(findings) == 1
    assert findings[0].object_name == "REPORT_TOP"


def test_a_column_named_keep_is_not_flagged():
    source = "CREATE TABLE t (keep NUMBER, dense_rank VARCHAR2(10));\n"
    assert find_keep_dense_rank(source) == []


def test_plain_dense_rank_window_function_is_not_flagged():
    # DENSE_RANK() OVER (...) is an ordinary window function that
    # PostgreSQL supports natively -- only the KEEP aggregate modifier
    # is the construct that doesn't convert.
    source = "SELECT DENSE_RANK() OVER (ORDER BY salary) FROM employees;\n"
    assert find_keep_dense_rank(source) == []
