# GAP-115: `TYPE ... IS REF CURSOR` becomes an invalid `CREATE TYPE ... AS REFCURSOR`

Oracle feature: a named cursor-variable type, weak (`IS REF CURSOR`) or
strong (`IS REF CURSOR RETURN rowtype`), declared in a package or a
routine and used for parameters, return values and variables.

## How it was found

`--load-check` on ora2pg's output for `docs/research/samples/connect_by_hierarchy_pkg.sql`,
which declares `TYPE refcursor IS REF CURSOR;` in its spec: the first
statement of the converted package did not load.

## Minimal example

```sql
CREATE OR REPLACE PACKAGE emp_api AS
  TYPE emp_cur IS REF CURSOR;
  TYPE emp_strong_cur IS REF CURSOR RETURN employees%ROWTYPE;
  FUNCTION list_all RETURN emp_cur;
END emp_api;
/
CREATE OR REPLACE PACKAGE BODY emp_api AS
  FUNCTION list_all RETURN emp_cur IS
    c emp_cur;
  BEGIN
    OPEN c FOR SELECT * FROM employees;
    RETURN c;
  END;
END emp_api;
/
```

In a live Oracle 23ai both compile and a caller fetches rows from
`emp_api.list_all`.

## ora2pg output (v25.0, `-t PACKAGE`)

The same for the hand-written source and for `DBMS_METADATA.GET_DDL`:

```sql
CREATE OR REPLACE TYPE emp_api.emp_cur AS REFCURSOR;
CREATE OR REPLACE TYPE emp_api.emp_strong_cur AS REFCURSOR RETURN employees%ROWTYPE;
CREATE OR REPLACE FUNCTION emp_api.list_all () RETURNS EMP_CUR AS $body$
DECLARE
    c emp_cur;
BEGIN
    OPEN c FOR SELECT * FROM employees;
    RETURN c;
  END;
$body$
```

## Observed problem

PostgreSQL 16 has no `CREATE OR REPLACE TYPE`, and `refcursor` is one
built-in type with no named variants, so neither type statement loads:

```
ERROR:  42601: syntax error at or near "TYPE"
```

and neither does any function that names the type:

```
ERROR:  42704: type "emp_cur" does not exist
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Delete the
type statements and write `refcursor` wherever the type is named. A strong
cursor loses its compile-time row type check; the rows it returns are the
same. `SYS_REFCURSOR` is not affected: ora2pg maps it to `refcursor`.

Implemented: `ora2pg_gap_report/detectors/ref_cursor_type.py`.
