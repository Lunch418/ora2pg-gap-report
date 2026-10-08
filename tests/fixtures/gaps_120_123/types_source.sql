CREATE TABLE gx_emp (emp_id NUMBER(6) PRIMARY KEY, salary NUMBER(8,2), name VARCHAR2(40));
INSERT INTO gx_emp VALUES (1, 100, 'a');
INSERT INTO gx_emp VALUES (2, 200, 'b');
COMMIT;
CREATE OR REPLACE PACKAGE gx_rec_pkg AS
  TYPE emp_rt IS RECORD (
    emp_id gx_emp.emp_id%TYPE,
    salary gx_emp.salary%TYPE
  );
  g_name_def VARCHAR2(40);
  SUBTYPE t_name IS g_name_def%TYPE;
  SUBTYPE t_sal IS gx_emp.salary%TYPE;
  FUNCTION top_salary RETURN NUMBER;
  FUNCTION label(p IN t_name) RETURN t_name;
END gx_rec_pkg;
/
CREATE OR REPLACE PACKAGE BODY gx_rec_pkg AS
  FUNCTION top_salary RETURN NUMBER IS
    r emp_rt;
    s t_sal;
  BEGIN
    SELECT emp_id, salary INTO r FROM gx_emp WHERE emp_id = 2;
    s := r.salary;
    RETURN s;
  END;
  FUNCTION label(p IN t_name) RETURN t_name IS
  BEGIN
    RETURN '<' || p || '>';
  END;
END gx_rec_pkg;
/
CREATE OR REPLACE PACKAGE gx_out_pkg AS
  PROCEDURE note(p IN VARCHAR2);
END gx_out_pkg;
/
CREATE OR REPLACE PACKAGE BODY gx_out_pkg AS
  PROCEDURE note(p IN VARCHAR2) IS BEGIN NULL; END;
END gx_out_pkg;
/
CREATE OR REPLACE PACKAGE gx_call_pkg AS
  PROCEDURE run_it(p IN VARCHAR2);
END gx_call_pkg;
/
CREATE OR REPLACE PACKAGE BODY gx_call_pkg AS
  PROCEDURE run_it(p IN VARCHAR2) IS
  BEGIN
    gx_out_pkg.note(p);
    gx_out_pkg.note('second ' || p);
  END;
END gx_call_pkg;
/
