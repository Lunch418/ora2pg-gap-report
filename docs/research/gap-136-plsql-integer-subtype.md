# GAP-136: PL/SQL integer subtypes are copied as they are

Oracle feature: PL/SQL's constrained integer subtypes `SIMPLE_INTEGER`, `NATURAL`, `NATURALN`, `POSITIVE`, `POSITIVEN`, `SIGNTYPE`.

## How it was found

While checking GAP-130..133: the same functions were run in Oracle 23ai and, after ora2pg 25.0, in PostgreSQL 16.

## Minimal example

`tests/fixtures/loud_types/oracle_functions.sql`, VALID in a live Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_l4(n NUMBER) RETURN NUMBER IS
  s SIMPLE_INTEGER := 1;
  k NATURAL := 2;
  p POSITIVE := 3;
  g SIGNTYPE := -1;
BEGIN
  RETURN s + k + p + g + n;
END;
/
```

## ora2pg output (v25.0, `-t FUNCTION`)

```sql
  s SIMPLE_INTEGER := 1;
  k NATURAL := 2;
  p POSITIVE := 3;
  g SIGNTYPE := -1;
```

`PLS_INTEGER` and `BINARY_INTEGER` become `integer`; these are copied.

## Observed problem

The function does not load:

```
ERROR:  type "simple_integer" does not exist
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Mechanical: `--fix` writes `integer` (`smallint` for `SIGNTYPE`) in declarations (`fix_plsql_integer_subtypes`), and the function loads and returns what Oracle does (`gx_l4(1)` = 6). The subtype's own constraint (not null, `> 0`, `>= 0`, -1..1) is not carried over: add a check where the code relies on it. A package specification's variables are GAP-036's and are not flagged here.

Implemented: `ora2pg_gap_report/detectors/plsql_integer_subtype.py`.
