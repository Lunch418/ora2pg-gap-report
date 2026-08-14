-- NOTE (ora2pg-gap-report research fixture, not pulled from an external repo):
-- We could not locate a real open-source PL/SQL *package* on GitHub that embeds
-- a CONNECT BY hierarchical query inside a function/procedure body (CONNECT BY
-- shows up constantly in ad-hoc SQL and views, rarely inside package code in the
-- public repos we searched: mortenbra/alexandria-plsql-utils, OraOpenSource/Logger,
-- oracle-samples/db-sample-schemas). To still exercise ora2pg's CONNECT BY handling
-- inside a package (the code path our tool cares about), we wrapped the canonical
-- Oracle EMP/DEPT hierarchical-query pattern (the same query that appears verbatim
-- across Oracle's own documentation and countless tutorials) in a minimal package.
-- This file is clearly a synthetic test fixture, assembled by us for step0 testing,
-- not a claim of a specific upstream repository.

CREATE OR REPLACE PACKAGE hierarchy_demo_pkg IS
  TYPE refcursor IS REF CURSOR;
  FUNCTION get_org_chart(p_top_employee_id IN NUMBER) RETURN refcursor;
END hierarchy_demo_pkg;
/

CREATE OR REPLACE PACKAGE BODY hierarchy_demo_pkg IS

  FUNCTION get_org_chart(p_top_employee_id IN NUMBER) RETURN refcursor IS
    l_cursor refcursor;
  BEGIN
    OPEN l_cursor FOR
      SELECT employee_id,
             manager_id,
             LEVEL AS depth,
             SYS_CONNECT_BY_PATH(last_name, '/') AS org_path
      FROM   employees
      START WITH employee_id = p_top_employee_id
      CONNECT BY PRIOR employee_id = manager_id;
    RETURN l_cursor;
  END get_org_chart;

END hierarchy_demo_pkg;
/
