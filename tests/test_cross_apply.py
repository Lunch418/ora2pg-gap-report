from ora2pg_gap_report.detectors.cross_apply import find_apply_joins


def test_cross_apply_is_flagged_inside_a_package_body():
    source = (
        "create or replace package body apply_pkg as\n"
        "  procedure latest_orders is\n"
        "    v_count number;\n"
        "  begin\n"
        "    select count(*) into v_count\n"
        "    from customers c\n"
        "    cross apply (\n"
        "      select o.order_id from orders o\n"
        "      where o.customer_id = c.customer_id\n"
        "      order by o.order_date desc\n"
        "      fetch first 1 rows only\n"
        "    ) latest;\n"
        "  end latest_orders;\n"
        "end apply_pkg;\n"
        "/\n"
    )
    findings = find_apply_joins(source)
    assert len(findings) == 1
    assert findings[0].object_name == "APPLY_PKG.LATEST_ORDERS"
    assert findings[0].snippet == "CROSS APPLY"
    assert findings[0].severity == "high"


def test_outer_apply_is_also_flagged():
    source = (
        "create or replace procedure noop as\n"
        "begin\n"
        "  select 1 from t outer apply (select 1 from dual) x;\n"
        "end;\n"
        "/\n"
    )
    findings = find_apply_joins(source)
    assert len(findings) == 1
    assert findings[0].snippet == "OUTER APPLY"


def test_ordinary_join_is_not_flagged():
    source = "select * from t1 cross join t2;\n"
    assert find_apply_joins(source) == []
