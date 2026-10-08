# GAP-114: a package constant built from another constant - the expression is garbled

Oracle feature: a package-level constant (or variable) whose initial value
is computed from another constant of the same package.

## How it was found

Not from a hypothesis: `--load-check` on ora2pg's real output for the
OraOpenSource Logger package (`docs/research/samples/logger.pkb`) showed
two functions failing with a syntax error no registered gap explained.
Logger declares

```sql
gc_date_format constant varchar2(255) := 'DD-MON-YYYY HH24:MI:SS';
gc_timestamp_format constant varchar2(255) := gc_date_format || ':FF';
```

and the functions that read `gc_timestamp_format` were the ones failing.

## Minimal example

```sql
CREATE OR REPLACE PACKAGE BODY fmt_pkg AS
  c_date CONSTANT VARCHAR2(30) := 'YYYY-MM-DD';
  c_stamp CONSTANT VARCHAR2(30) := c_date || ' HH24:MI';

  FUNCTION stamp_fmt RETURN VARCHAR2 IS
  BEGIN
    RETURN c_stamp;
  END;
END fmt_pkg;
/
```

In a live Oracle 23ai the package compiles and `fmt_pkg.stamp_fmt` returns
`YYYY-MM-DD HH24:MI`.

## ora2pg output (v25.0, `-t PACKAGE`)

From the hand-written source:

```sql
CREATE OR REPLACE FUNCTION fmt_pkg.stamp_fmt () RETURNS varchar AS $body$
BEGIN
    RETURN current_setting('fmt_pkg.c_stamp')::varchar(30)current_setting('fmt_pkg.c_date')::varchar(30)||;
  END;
$body$
LANGUAGE PLPGSQL
```

From the same package exported with `DBMS_METADATA.GET_DDL`:

```sql
    RETURN current_setting('fmt_pkg.c_stamp')::varchar(30)c_date||;
```

ora2pg rewrites every read of a package variable into `current_setting()`
(the GAP-036 emulation). For a constant whose initializer names another
constant, it appends the initializer's own pieces after the first
reference, with the `||` left dangling at the end.

## Observed problem

The function does not load into PostgreSQL 16:

```
ERROR:  42601: syntax error at or near "("
```

Every routine that reads the constant fails the same way. A constant with
a literal initializer is not affected by this gap (it still has GAP-036's
problem of never being set).

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Replace the
constant with an `IMMUTABLE` function that returns the finished value
(see the [package state recipe](../recipes/package-state.md)), or compute
the value where it is used.

Implemented: `ora2pg_gap_report/detectors/package_constant_chain.py` -
reads the package's own declare section (spec or body) and flags a
declaration whose initializer names an earlier one.
