CREATE OR REPLACE PACKAGE gx_t_pkg AS
  SUBTYPE t_code IS VARCHAR2(10);
  TYPE pair_rt IS RECORD (a NUMBER(6), b VARCHAR2(10));
  TYPE num_tt IS TABLE OF NUMBER INDEX BY PLS_INTEGER;
  FUNCTION code_of(p IN t_code) RETURN t_code;
  FUNCTION pair_sum RETURN NUMBER;
  FUNCTION tab_count RETURN NUMBER;
END gx_t_pkg;
/
CREATE OR REPLACE PACKAGE BODY gx_t_pkg AS
  FUNCTION code_of(p IN t_code) RETURN t_code IS
    v t_code := p;
  BEGIN
    RETURN v || '!';
  END;
  FUNCTION pair_sum RETURN NUMBER IS
    r pair_rt;
  BEGIN
    r.a := 2;
    r.b := '3';
    RETURN r.a + TO_NUMBER(r.b);
  END;
  FUNCTION tab_count RETURN NUMBER IS
    t num_tt;
  BEGIN
    t(1) := 5;
    t(2) := 6;
    RETURN t.COUNT;
  END;
END gx_t_pkg;
/
CREATE OR REPLACE PACKAGE gx_ext_pkg AS
  PROCEDURE run_it;
END gx_ext_pkg;
/
CREATE OR REPLACE PACKAGE BODY gx_ext_pkg AS
  PROCEDURE run_it IS
  BEGIN
    DBMS_OUTPUT.PUT_LINE('a');
    DBMS_SESSION.SLEEP(0);
    DBMS_APPLICATION_INFO.SET_MODULE('m', 'a');
    DBMS_APPLICATION_INFO.SET_ACTION('x');
    DBMS_STATS.GATHER_TABLE_STATS(USER, 'GX_EMP');
    DBMS_SCHEDULER.RUN_JOB('J1');
    UTL_FILE.FCLOSE_ALL;
    gx_out_pkg.note('x');
    HTP.P('x');
    OWA_UTIL.MIME_HEADER('text/plain');
    DBMS_UTILITY.EXEC_DDL_STATEMENT('x');
  END;
END gx_ext_pkg;
/
