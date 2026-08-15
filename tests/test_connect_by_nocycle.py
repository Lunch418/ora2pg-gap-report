from ora2pg_gap_report.detectors.connect_by_nocycle import (
    find_connect_by_nocycle_or_order_siblings,
)


def test_connect_by_nocycle_is_flagged():
    source = (
        "create or replace procedure build_tree as\n"
        "begin\n"
        "  for r in (select employee_id from employees\n"
        "            connect by nocycle prior employee_id = manager_id) loop\n"
        "    null;\n"
        "  end loop;\n"
        "end;\n"
        "/\n"
    )
    findings = find_connect_by_nocycle_or_order_siblings(source)
    assert len(findings) == 1
    assert findings[0].object_name == "BUILD_TREE"
    assert findings[0].snippet == "CONNECT BY NOCYCLE"
    assert findings[0].severity == "high"


def test_order_siblings_by_is_flagged():
    source = (
        "create or replace procedure build_tree as\n"
        "begin\n"
        "  for r in (select employee_id from employees\n"
        "            start with manager_id is null\n"
        "            connect by prior employee_id = manager_id\n"
        "            order siblings by employee_id) loop\n"
        "    null;\n"
        "  end loop;\n"
        "end;\n"
        "/\n"
    )
    findings = find_connect_by_nocycle_or_order_siblings(source)
    assert len(findings) == 1
    assert findings[0].snippet == "ORDER SIBLINGS BY"


def test_both_in_the_same_query_yield_two_findings():
    source = (
        "create or replace procedure build_tree as\n"
        "begin\n"
        "  for r in (select employee_id from employees\n"
        "            connect by nocycle prior employee_id = manager_id\n"
        "            order siblings by employee_id) loop\n"
        "    null;\n"
        "  end loop;\n"
        "end;\n"
        "/\n"
    )
    findings = find_connect_by_nocycle_or_order_siblings(source)
    assert len(findings) == 2


def test_plain_connect_by_without_nocycle_is_not_flagged():
    source = (
        "create or replace procedure build_tree as\n"
        "begin\n"
        "  for r in (select employee_id from employees\n"
        "            connect by prior employee_id = manager_id) loop\n"
        "    null;\n"
        "  end loop;\n"
        "end;\n"
        "/\n"
    )
    assert find_connect_by_nocycle_or_order_siblings(source) == []
