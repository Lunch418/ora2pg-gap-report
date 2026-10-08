CREATE OR REPLACE PACKAGE gx_e_pkg AS
  SUBTYPE t_code IS VARCHAR2(10);
  SUBTYPE t_emp IS gx_emp%ROWTYPE;
  TYPE emp2_rt IS RECORD (e gx_emp%ROWTYPE, n NUMBER);
  PROCEDURE run_it;
  FUNCTION q(p IN gx_e_pkg.t_code) RETURN gx_e_pkg.t_code;
END gx_e_pkg;
/
CREATE OR REPLACE PACKAGE BODY gx_e_pkg AS
  PROCEDURE run_it IS
    c INTEGER;
  BEGIN
    DBMS_OUTPUT.DISABLE;
    DBMS_OUTPUT.ENABLE(1000);
    c := DBMS_SQL.OPEN_CURSOR;
    DBMS_SQL.CLOSE_CURSOR(c);
    SYS.DBMS_SESSION.SLEEP(0.1);
    IF c IS NULL THEN DBMS_SESSION.SLEEP(1); END IF;
    DBMS_APPLICATION_INFO.SET_MODULE(module_name => 'm', action_name => NULL);
  END;
  FUNCTION q(p IN gx_e_pkg.t_code) RETURN gx_e_pkg.t_code IS
    v gx_e_pkg.t_code := p;
  BEGIN
    RETURN v;
  END;
END gx_e_pkg;
/
CREATE OR REPLACE TRIGGER gx_e_trg BEFORE INSERT ON gx_emp FOR EACH ROW
BEGIN
  DBMS_SESSION.SLEEP(0);
  HTP.P('x');
END;
/
