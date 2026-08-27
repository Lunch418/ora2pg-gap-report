from ora2pg_gap_report.detectors.connect_by_pseudocolumn import find_connect_by_pseudocolumns


def test_connect_by_root_and_isleaf_are_both_flagged():
    source = (
        "CREATE OR REPLACE VIEW v_emp_tree AS\n"
        "SELECT employee_id,\n"
        "       CONNECT_BY_ROOT last_name AS root_name,\n"
        "       CONNECT_BY_ISLEAF AS is_leaf\n"
        "FROM employees\n"
        "START WITH manager_id IS NULL\n"
        "CONNECT BY PRIOR employee_id = manager_id;\n"
    )
    findings = find_connect_by_pseudocolumns(source)
    assert len(findings) == 2
    assert {f.snippet for f in findings} == {"CONNECT_BY_ROOT", "CONNECT_BY_ISLEAF"}
    assert all(f.object_name == "V_EMP_TREE" for f in findings)
    assert all(f.severity == "high" for f in findings)


def test_connect_by_iscycle_is_flagged():
    source = (
        "create or replace view v_cycle as\n"
        "select emp_id, connect_by_iscycle as is_cycle\n"
        "from emps connect by nocycle prior emp_id = mgr_id;\n"
    )
    findings = find_connect_by_pseudocolumns(source)
    assert len(findings) == 1
    assert findings[0].snippet == "CONNECT_BY_ISCYCLE"


def test_sys_connect_by_path_is_not_flagged():
    # ora2pg genuinely converts SYS_CONNECT_BY_PATH into a working string
    # concatenation inside the recursive CTE it generates (verified against
    # a real ora2pg 25.0 + PostgreSQL 16 run) -- flagging it would be a
    # false positive on a construct that migrates fine.
    source = (
        "CREATE OR REPLACE VIEW v_path AS\n"
        "SELECT SYS_CONNECT_BY_PATH(last_name, '/') AS path\n"
        "FROM employees CONNECT BY PRIOR employee_id = manager_id;\n"
    )
    assert find_connect_by_pseudocolumns(source) == []


def test_plain_connect_by_without_pseudocolumns_is_not_flagged():
    source = (
        "SELECT employee_id FROM employees\n"
        "START WITH manager_id IS NULL\n"
        "CONNECT BY PRIOR employee_id = manager_id;\n"
    )
    assert find_connect_by_pseudocolumns(source) == []
