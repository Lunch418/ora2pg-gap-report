from ora2pg_gap_report.detectors.model_clause import find_model_clauses


def test_model_clause_is_flagged_inside_a_package_body():
    source = """
    create or replace package body sales_forecast_pkg as
      procedure forecast_next_quarter is
        cursor c is
          select product_id, quarter, sales
          from sales_history
          model
            partition by (product_id)
            dimension by (quarter)
            measures (sales)
            rules (
              sales[4] = sales[3] * 1.1
            );
      begin
        for r in c loop null; end loop;
      end forecast_next_quarter;
    end sales_forecast_pkg;
    /
    """
    findings = find_model_clauses(source)
    assert len(findings) == 1
    assert findings[0].object_name == "SALES_FORECAST_PKG.FORECAST_NEXT_QUARTER"
    assert findings[0].severity == "high"


def test_unrelated_model_identifier_is_not_a_false_positive():
    # A variable or column literally named "model" (or "model_count"),
    # unrelated to the SQL MODEL clause, must not trigger this detector —
    # only MODEL immediately followed by PARTITION BY/DIMENSION BY/MEASURES
    # is the actual construct.
    source = """
    create or replace procedure noop as
      v_model varchar2(50) := 'Model X';
      model_count number;
    begin
      null;
    end noop;
    /
    """
    assert find_model_clauses(source) == []


def test_string_and_comment_content_does_not_trigger_a_false_positive():
    source = """
    create or replace procedure noop as
    begin
      -- uses model partition by (x) dimension by (y) as an example
      null;
    end noop;
    /
    """
    assert find_model_clauses(source) == []


def test_partitioned_outer_join_alias_named_model_is_not_a_false_positive():
    # Oracle's *unrelated* partitioned outer join syntax can have a table
    # alias literally named "model" immediately followed by its own
    # PARTITION BY clause -- this must not be mistaken for the MODEL
    # clause (which additionally requires MEASURES/RULES, absent here).
    source = """
    create or replace procedure noop as
    begin
      for r in (
        select * from sales_history model
        partition by (model.product_id)
        right outer join calendar c on (1=1)
      ) loop null; end loop;
    end noop;
    /
    """
    assert find_model_clauses(source) == []


def test_model_clause_with_main_name_is_still_detected():
    # MODEL's optional 'MAIN <name>' clause means MEASURES/DIMENSION BY
    # don't immediately follow the MODEL keyword itself.
    source = """
    create or replace procedure noop as
    begin
      for r in (
        select * from sales_history
        model main my_model
        dimension by (quarter)
        measures (sales)
        rules (sales[4] = sales[3] * 1.1)
      ) loop null; end loop;
    end noop;
    /
    """
    findings = find_model_clauses(source)
    assert len(findings) == 1
