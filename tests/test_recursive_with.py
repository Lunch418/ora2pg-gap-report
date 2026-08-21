from ora2pg_gap_report.detectors.recursive_with import find_recursive_with_missing_keyword


def test_native_recursive_with_missing_keyword_is_flagged():
    source = (
        "create or replace package body rec_pkg as\n"
        "  procedure walk_tree is\n"
        "    v_count number;\n"
        "  begin\n"
        "    with tree (employee_id, manager_id) as (\n"
        "      select employee_id, manager_id from employees where manager_id is null\n"
        "      union all\n"
        "      select e.employee_id, e.manager_id\n"
        "      from employees e, tree t\n"
        "      where e.manager_id = t.employee_id\n"
        "    )\n"
        "    select count(*) into v_count from tree;\n"
        "  end walk_tree;\n"
        "end rec_pkg;\n"
        "/\n"
    )
    findings = find_recursive_with_missing_keyword(source)
    assert len(findings) == 1
    assert findings[0].object_name == "REC_PKG.WALK_TREE"
    assert findings[0].snippet == "WITH TREE AS (...)"
    assert findings[0].severity == "high"


def test_with_recursive_already_present_is_not_flagged():
    source = (
        "create or replace procedure walk_tree as\n"
        "  v_count number;\n"
        "begin\n"
        "  with recursive tree (employee_id, manager_id) as (\n"
        "    select employee_id, manager_id from employees where manager_id is null\n"
        "    union all\n"
        "    select e.employee_id, e.manager_id\n"
        "    from employees e, tree t\n"
        "    where e.manager_id = t.employee_id\n"
        "  )\n"
        "  select count(*) into v_count from tree;\n"
        "end;\n"
        "/\n"
    )
    assert find_recursive_with_missing_keyword(source) == []


def test_ordinary_non_recursive_union_cte_is_not_flagged():
    # A plain CTE using UNION for concatenation, no self-reference --
    # must not be mistaken for recursion.
    source = (
        "create or replace procedure noop as\n"
        "  v_count number;\n"
        "begin\n"
        "  with combined as (\n"
        "    select id from active_orders\n"
        "    union all\n"
        "    select id from archived_orders\n"
        "  )\n"
        "  select count(*) into v_count from combined;\n"
        "end;\n"
        "/\n"
    )
    assert find_recursive_with_missing_keyword(source) == []


def test_cte_without_any_union_is_not_flagged():
    source = (
        "create or replace procedure noop as\n"
        "  v_count number;\n"
        "begin\n"
        "  with recent as (select id from orders where status = 'OPEN')\n"
        "  select count(*) into v_count from recent;\n"
        "end;\n"
        "/\n"
    )
    assert find_recursive_with_missing_keyword(source) == []


def test_self_reference_inside_a_nested_from_subquery_is_still_detected():
    # A nested subquery in the FROM clause with its own WHERE clause used
    # to be treated as the boundary of the "FROM clause" being scanned,
    # truncating the search before it ever reached the real self-reference
    # sitting after that subquery.
    source = (
        "create or replace procedure noop as\n"
        "  v_count number;\n"
        "begin\n"
        "  with tree (id) as (\n"
        "    select id from employees where mgr is null\n"
        "    union all\n"
        "    select e.id from (select * from employees where active = 1) e, tree t\n"
        "    where e.mgr = t.id\n"
        "  )\n"
        "  select count(*) into v_count from tree;\n"
        "end;\n"
        "/\n"
    )
    findings = find_recursive_with_missing_keyword(source)
    assert len(findings) == 1


def test_self_reference_in_a_third_union_branch_is_still_detected():
    # More than one non-recursive branch before the recursive one -- the
    # self-reference doesn't have to be in the branch right after the
    # first UNION.
    source = (
        "create or replace procedure noop as\n"
        "  v_count number;\n"
        "begin\n"
        "  with tree (id) as (\n"
        "    select id from roots\n"
        "    union all\n"
        "    select id from level1\n"
        "    union all\n"
        "    select e.id from employees e, tree t where e.mgr = t.id\n"
        "  )\n"
        "  select count(*) into v_count from tree;\n"
        "end;\n"
        "/\n"
    )
    findings = find_recursive_with_missing_keyword(source)
    assert len(findings) == 1


def test_schema_qualified_table_sharing_the_cte_name_is_not_a_false_positive():
    # 'archive.orders' is an unrelated, schema-qualified real table that
    # happens to share the CTE's bare name -- must not be mistaken for a
    # self-reference just because 'orders' appears as a substring after
    # the dot.
    source = (
        "create or replace procedure noop as\n"
        "  v_count number;\n"
        "begin\n"
        "  with orders as (\n"
        "    select id from recent_orders\n"
        "    union all\n"
        "    select o.id from archive.orders o where o.status = 'X'\n"
        "  )\n"
        "  select count(*) into v_count from orders;\n"
        "end;\n"
        "/\n"
    )
    assert find_recursive_with_missing_keyword(source) == []


def test_cte_name_reused_as_a_column_alias_is_not_a_false_positive():
    # The CTE name reappearing after UNION as a bare column alias (not
    # preceded by FROM/JOIN) must not be mistaken for a self-reference.
    source = (
        "create or replace procedure noop as\n"
        "  v_count number;\n"
        "begin\n"
        "  with x as (\n"
        "    select 1 as val from dual\n"
        "    union all\n"
        "    select 2 as x from other_table\n"
        "  )\n"
        "  select count(*) into v_count from x;\n"
        "end;\n"
        "/\n"
    )
    assert find_recursive_with_missing_keyword(source) == []


def test_recursive_cte_not_first_in_the_with_list_is_still_detected():
    # 'WITH seed AS (...), tree AS (...)' -- a non-recursive anchor/seed
    # CTE listed before the recursive one is a common real-world shape.
    # _WITH_CTE_RE alone only ever matches the first CTE (it requires a
    # literal WITH right before the name), so 'tree' here -- preceded by
    # ', ' from the previous CTE's closing ')', not WITH -- used to be
    # missed entirely.
    source = (
        "create or replace procedure walk_tree as\n"
        "  v_count number;\n"
        "begin\n"
        "  with seed as (\n"
        "    select employee_id from employees where employee_id = 1\n"
        "  ),\n"
        "  tree (employee_id, manager_id) as (\n"
        "    select employee_id, manager_id from employees where manager_id is null\n"
        "    union all\n"
        "    select e.employee_id, e.manager_id\n"
        "    from employees e, tree t\n"
        "    where e.manager_id = t.employee_id\n"
        "  )\n"
        "  select count(*) into v_count from tree;\n"
        "end walk_tree;\n"
        "/\n"
    )
    findings = find_recursive_with_missing_keyword(source)
    # Exactly 1, not 2: 'seed' itself (no UNION, no self-reference) must
    # not be flagged just because it shares a WITH list with 'tree'.
    assert len(findings) == 1
    assert findings[0].snippet == "WITH TREE AS (...)"
