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


def test_real_open_source_excelgen_with_function_is_flagged():
    # Found scanning mbleron/ExcelGen (github.com/mbleron/ExcelGen), a
    # real, actively-maintained Oracle PL/SQL Excel generator library --
    # this project's first real-corpus confirmation of GAP-010, distinct
    # from the earlier synthetic-only test above. Verbatim excerpt (not
    # paraphrased) of test_cases/test_bin_double.sql: a top-level SQL
    # statement (not inside any named PACKAGE/PROCEDURE/TRIGGER/VIEW),
    # using WITH FUNCTION to define get_xlsx() inline and call it from the
    # query that follows -- object_name is correctly 'UNKNOWN' here, not a
    # bug: there is genuinely no enclosing named object for a bare
    # top-level statement like this one.
    source = """
WITH 
FUNCTION get_xlsx(p_src SYS_REFCURSOR) RETURN BLOB AS
    v_blob          BLOB;
    v_ctxId         ExcelGen.ctxHandle;
    v_sheetHandle   BINARY_INTEGER;
BEGIN
        v_ctxId := ExcelGen.createContext();
        v_sheetHandle := ExcelGen.addSheetFromCursor(v_ctxId, 'Employee Salaries', p_src, p_sheetIndex => 1);
        -- freeze the top row with the column headers
        ExcelGen.setHeader(v_ctxId, v_sheetHandle, p_frozen => TRUE);
        -- style with alternating colors on each row. 
        ExcelGen.setTableFormat(v_ctxId, v_sheetHandle, 'TableStyleLight2');
        -- single column format on the salary column. The ID column keeps default format
        ExcelGen.setColumnFormat(
            p_ctxId     => v_ctxId
            ,p_sheetId  => v_sheetHandle
            ,p_columnId => 5        -- the salary column
            ,p_format   => '$#,##0.00'
        );
        v_blob := ExcelGen.getFileContent(v_ctxId);
        ExcelGen.closeContext(v_ctxId);
        RETURN v_blob;
END;
-- begin sql portion 
add_bilbo AS (
    SELECT e.employee_id AS employee_id, e.last_name, e.first_name, d.department_name, e.salary
    FROM hr.employees e
    INNER JOIN hr.departments d
        ON d.department_id = e.department_id
    UNION ALL
    SELECT 999 AS employee_id, 'Baggins' As last_name, 'Bilbo' as first_name, 'Sales' AS department_name
        ,123.45 AS salary
    FROM dual
), emp_curs AS (
    SELECT employee_id, last_name, first_name, department_name
                ,TO_BINARY_DOUBLE(salary) AS salary
    FROM add_bilbo ORDER BY last_name, first_name
) SELECT get_xlsx(CURSOR(SELECT * FROM emp_curs)) FROM DUAL
;
/
    """
    findings = find_with_function_clauses(source)
    assert len(findings) == 1
    assert findings[0].object_name == "UNKNOWN"
    assert findings[0].snippet == "WITH FUNCTION"
