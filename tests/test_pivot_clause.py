from ora2pg_gap_report.detectors.pivot_clause import find_pivot_clauses


def test_pivot_is_flagged_inside_a_package_body():
    source = """
    create or replace package body sales_report_pkg as
      procedure quarterly_report is
        cursor c is
          select * from (select product_id, quarter, sales from sales_history)
          pivot (sum(sales) for quarter in ('Q1' as q1, 'Q2' as q2));
      begin
        for r in c loop null; end loop;
      end quarterly_report;
    end sales_report_pkg;
    /
    """
    findings = find_pivot_clauses(source)
    assert len(findings) == 1
    assert findings[0].object_name == "SALES_REPORT_PKG.QUARTERLY_REPORT"
    assert findings[0].snippet == "PIVOT"
    assert findings[0].severity == "high"


def test_unpivot_is_also_flagged():
    source = """
    create or replace procedure noop as
    begin
      for r in (
        select * from quarterly_sales
        unpivot (sales for quarter in (q1, q2, q3, q4))
      ) loop null; end loop;
    end noop;
    /
    """
    findings = find_pivot_clauses(source)
    assert len(findings) == 1
    assert findings[0].snippet == "UNPIVOT"


def test_pivot_used_as_a_bare_identifier_is_not_a_false_positive():
    # PIVOT/UNPIVOT are only the SQL clause when immediately followed by
    # '(' -- a variable merely named "pivot" isn't the construct.
    source = """
    create or replace procedure noop as
      v_pivot number;
    begin
      v_pivot := 1;
    end noop;
    /
    """
    assert find_pivot_clauses(source) == []


def test_string_and_comment_content_does_not_trigger_a_false_positive():
    source = """
    create or replace procedure noop as
    begin
      -- see pivot(...) example in the docs
      null;
    end noop;
    /
    """
    assert find_pivot_clauses(source) == []


def test_pivot_xml_variant_is_detected():
    # PIVOT XML (a dynamic/unknown IN-list) is real, documented Oracle
    # syntax -- the same underlying gap as plain PIVOT.
    source = """
    create or replace procedure noop as
    begin
      for r in (
        select * from (select product_id, quarter, sales from sales_history)
        pivot xml (sum(sales) for quarter in (select distinct quarter from sales_history))
      ) loop null; end loop;
    end noop;
    /
    """
    findings = find_pivot_clauses(source)
    assert len(findings) == 1
    assert findings[0].snippet == "PIVOT"


def test_unpivot_include_exclude_nulls_variants_are_detected():
    source = """
    create or replace procedure noop as
    begin
      for r in (
        select * from quarterly_sales
        unpivot include nulls (sales for quarter in (q1, q2))
      ) loop null; end loop;
    end noop;
    /
    """
    findings = find_pivot_clauses(source)
    assert len(findings) == 1
    assert findings[0].snippet == "UNPIVOT"
