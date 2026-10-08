# GAP-120: `%TYPE` in a package RECORD or SUBTYPE is copied into DDL

Oracle feature: a package-level type anchored to a column or a variable -
a RECORD field `salary gx_emp.salary%TYPE`, or `SUBTYPE t_name IS
g_name_def%TYPE`, `SUBTYPE t_emp IS gx_emp%ROWTYPE`.

## How it was found

`--migrate --load-check docker` on the sample packages
(`docs/research/samples/`): four `syntax error at or near "%"` errors that
no gap explained - `equitable_salaries_pkg.id_salary_rt` (in
`compound_trigger_dlee.sql`) and the three subtypes of alexandria-plsql-
utils' `file_util_pkg`. OraOpenSource Logger's `rec_logger_log` has the
same shape.

## Minimal example

`tests/fixtures/gaps_120_123/types_source.sql`:

```sql
CREATE TABLE gx_emp (emp_id NUMBER(6) PRIMARY KEY, salary NUMBER(8,2), name VARCHAR2(40));
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
```

with a body using both (the full file is in the fixture). In a live
Oracle 23ai the package is VALID, `top_salary` returns 200 and
`label('x')` returns `<x>`.

## ora2pg output (v25.0, `-t PACKAGE`)

```sql
CREATE TYPE gx_rec_pkg.emp_rt AS (
emp_id gx_emp.emp_id%TYPE,
    salary gx_emp.salary%TYPE
);
CREATE DOMAIN gx_rec_pkg.t_name AS g_name_def%TYPE;
CREATE DOMAIN gx_rec_pkg.t_sal AS gx_emp.salary%TYPE;
```

`%ROWTYPE` is copied the same way: `CREATE DOMAIN gx_e_pkg.t_emp AS
gx_emp%ROWTYPE`, `e gx_emp%ROWTYPE` in a CREATE TYPE.

## Observed problem

`%TYPE` is PL/pgSQL declaration syntax; SQL DDL does not have it, so
PostgreSQL 16 rejects all three statements:

```
ERROR:  42601: syntax error at or near "%"
```

and every routine that uses the types fails after them.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Write the
anchored column's or variable's type in its place (`numeric(8,2)`,
`varchar(40)`); for `%ROWTYPE`, the table's own row type (`gx_emp`).
Written that way, the fixture loads and behaves the same as in Oracle
(`tests/test_gaps_120_123_load.py`).

Only package-level declarations: a type declared inside a routine stays a
PL/pgSQL declaration, where `%TYPE` is valid.

Implemented: `ora2pg_gap_report/detectors/package_type_anchor.py`;
`--load-check` recognises the copied anchor in a `CREATE TYPE`/`CREATE
DOMAIN`.
