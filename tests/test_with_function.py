from ora2pg_gap_report.detectors.with_function import find_with_function_clauses


def test_with_function_is_flagged_inside_a_package_body():
    source = """
    create or replace package body calc_pkg as
      procedure run_calc is
        v_total number;
      begin
        with
          function apply_discount(p_amount number) return number is
          begin
            return p_amount * 0.9;
          end;
        select sum(apply_discount(amount)) into v_total from orders;
      end run_calc;
    end calc_pkg;
    /
    """
    findings = find_with_function_clauses(source)
    assert len(findings) == 1
    assert findings[0].object_name == "CALC_PKG.RUN_CALC"
    assert findings[0].snippet == "with function"
    assert findings[0].severity == "high"


def test_with_procedure_is_also_flagged():
    source = """
    create or replace procedure noop as
    begin
      with
        procedure log_it(p_msg varchar2) is
        begin
          null;
        end;
      begin
        log_it('hi');
      end;
    end noop;
    /
    """
    findings = find_with_function_clauses(source)
    assert len(findings) == 1
    assert findings[0].snippet == "with procedure"


def test_ordinary_with_cte_is_not_a_false_positive():
    source = """
    create or replace procedure noop as
    begin
      with cte as (select 1 as x from dual)
      select * from cte;
    end noop;
    /
    """
    assert find_with_function_clauses(source) == []
