from ora2pg_gap_report.detectors.read_only_view import find_read_only_views


def test_a_read_only_view_is_flagged():
    source = (
        "CREATE OR REPLACE VIEW v_emp AS\n"
        "  SELECT emp_id, name FROM employees\n"
        "  WITH READ ONLY;\n"
    )
    findings = find_read_only_views(source)
    assert len(findings) == 1
    assert findings[0].object_name == "V_EMP"
    assert findings[0].snippet == "WITH READ ONLY"
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_a_force_view_is_matched_too():
    source = "CREATE OR REPLACE FORCE VIEW v AS SELECT 1 AS a FROM dual WITH READ ONLY;\n"
    assert len(find_read_only_views(source)) == 1


def test_an_ordinary_view_is_not_flagged():
    assert find_read_only_views("CREATE VIEW v AS SELECT emp_id FROM employees;\n") == []


def test_with_check_option_is_not_flagged():
    # A different clause that PostgreSQL does support.
    source = "CREATE VIEW v AS SELECT a FROM t WHERE a > 0 WITH CHECK OPTION;\n"
    assert find_read_only_views(source) == []


def test_the_clause_is_attributed_to_its_own_view_among_several():
    source = (
        "CREATE VIEW v_one AS SELECT a FROM t;\n"
        "CREATE VIEW v_two AS SELECT b FROM t WITH READ ONLY;\n"
        "CREATE VIEW v_three AS SELECT c FROM t;\n"
    )
    findings = find_read_only_views(source)
    assert len(findings) == 1
    assert findings[0].object_name == "V_TWO"


def test_real_oracle_sample_schema_hr_view_is_flagged():
    # Real shape from Oracle's own db-sample-schemas
    # (human_resources/hr_create.sql): EMP_DETAILS_VIEW, declared read
    # only in Oracle and silently writable after conversion.
    source = (
        "CREATE OR REPLACE VIEW emp_details_view\n"
        "  (employee_id, job_id, manager_id, department_id)\n"
        "AS SELECT e.employee_id, e.job_id, e.manager_id, e.department_id\n"
        "   FROM employees e\n"
        "WITH READ ONLY;\n"
    )
    findings = find_read_only_views(source)
    assert len(findings) == 1
    assert findings[0].object_name == "EMP_DETAILS_VIEW"
