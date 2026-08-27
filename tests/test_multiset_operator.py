from ora2pg_gap_report.detectors.multiset_operator import find_multiset_operators


def test_multiset_union_and_member_of_are_both_flagged():
    source = (
        "CREATE OR REPLACE VIEW v_multiset AS\n"
        "SELECT id, col_a MULTISET UNION col_b AS merged\n"
        "FROM basket_data\n"
        "WHERE 5 MEMBER OF col_a;\n"
    )
    findings = find_multiset_operators(source)
    assert len(findings) == 2
    assert {f.snippet for f in findings} == {"MULTISET UNION", "MEMBER OF"}
    assert all(f.object_name == "V_MULTISET" for f in findings)
    assert all(f.severity == "high" for f in findings)


def test_cast_multiset_subquery_idiom_is_flagged():
    source = (
        "create or replace view v_cast_ms as\n"
        "select d.dept_id,\n"
        "       cast(multiset(select e.emp_id from emps e "
        "where e.dept_id = d.dept_id) as num_list_t) as emp_ids\n"
        "from depts d;\n"
    )
    findings = find_multiset_operators(source)
    assert len(findings) == 1
    assert findings[0].snippet == "CAST(MULTISET("


def test_submultiset_and_multiset_intersect_are_flagged():
    source = (
        "SELECT id FROM basket\n"
        "WHERE col_a SUBMULTISET OF col_b\n"
        "   OR col_a MULTISET INTERSECT col_b IS NOT NULL;\n"
    )
    findings = find_multiset_operators(source)
    assert len(findings) == 2
    assert {f.snippet for f in findings} == {"SUBMULTISET OF", "MULTISET INTERSECT"}


def test_member_function_declaration_is_not_flagged():
    # MEMBER FUNCTION / MEMBER PROCEDURE are ordinary object-type method
    # declarations, unrelated to collection membership -- requiring the
    # following OF keeps them out.
    source = (
        "CREATE OR REPLACE TYPE person_typ AS OBJECT (\n"
        "  name VARCHAR2(50),\n"
        "  MEMBER FUNCTION greet RETURN VARCHAR2,\n"
        "  MEMBER PROCEDURE touch\n"
        ");\n"
    )
    assert find_multiset_operators(source) == []


def test_real_utplsql_multiset_union_all_is_flagged():
    # Real shape from utPLSQL's source/core/ut_suite_builder.pkb -- the
    # MULTISET UNION ALL variant, used on both sides of an assignment.
    source = (
        "create or replace package body ut_suite_builder is\n"
        "  procedure propagate_before_after_each is\n"
        "  begin\n"
        "    l_test.before_each_list := convert_list(a_before_each_list) "
        "multiset union all l_test.before_each_list;\n"
        "  end;\n"
        "end ut_suite_builder;\n"
        "/\n"
    )
    findings = find_multiset_operators(source)
    assert len(findings) == 1
    assert findings[0].snippet == "MULTISET UNION"
    assert findings[0].object_name == "UT_SUITE_BUILDER.PROPAGATE_BEFORE_AFTER_EACH"
