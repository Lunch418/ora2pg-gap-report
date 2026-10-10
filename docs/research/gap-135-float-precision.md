# GAP-135: `FLOAT(n)` in PL/SQL becomes `double precision(n)`

Oracle feature: `FLOAT(n)`, a NUMBER subtype with a binary precision, declared in PL/SQL.

## How it was found

While checking GAP-130..133: the same functions were run in Oracle 23ai and, after ora2pg 25.0, in PostgreSQL 16.

## Minimal example

`tests/fixtures/loud_types/oracle_functions.sql`, VALID in a live Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_l3(n NUMBER) RETURN NUMBER IS
  f FLOAT(10) := n;
BEGIN
  RETURN f * 2;
END;
/
```

## ora2pg output (v25.0, `-t FUNCTION`)

```sql
  f double precision(10) := n;
```

A column `FLOAT(10)` becomes plain `double precision`; in PL/SQL the precision is kept.

## Observed problem

The function does not load:

```
ERROR:  syntax error at or near "("
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Mechanical: `--fix` drops the precision (`fix_double_precision_length` in `ora2pg_gap_report/autofix.py`), and the function loads and returns what Oracle does (`gx_l3(2)` = 4). `--load-check` reports the error as fixable.

Implemented: `ora2pg_gap_report/detectors/float_precision.py`.
