# GAP-134: `TRUNC` of a number becomes `date_trunc`

Oracle feature: `TRUNC` takes a date or a number. `TRUNC(10 / 3)` is 3, `TRUNC(3.14159, 2)` is 3.14.

## How it was found

While checking GAP-130..133: the same functions were run in Oracle 23ai and, after ora2pg 25.0, in PostgreSQL 16.

## Minimal example

`tests/fixtures/loud_types/oracle_functions.sql`, VALID in a live Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_l1(n NUMBER) RETURN NUMBER IS
BEGIN
  RETURN TRUNC(n / 3);
END;
/
CREATE OR REPLACE FUNCTION gx_l2(n NUMBER) RETURN NUMBER IS
BEGIN
  RETURN TRUNC(n, 2);
END;
/
```

## ora2pg output (v25.0, `-t FUNCTION`)

```sql
  RETURN date_trunc('day', n / 3);
...
  RETURN date_trunc(2, n);
```

ora2pg rewrites every `TRUNC` as a date's, whatever its argument: `TRUNC(n)`, `TRUNC(ABS(n))`, `TRUNC(TO_NUMBER(s))` all become `date_trunc('day', ...)`.

## Observed problem

Both functions load, and the first call fails:

```
ERROR:  function date_trunc(unknown, bigint) does not exist
```

Found in OraOpenSource Logger: `trunc((p_date_stop-p_date_start)/7) || ' weeks'`.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** Replace `date_trunc` with `trunc`. The detector flags `TRUNC` whose argument is visibly a number: a numeric literal, a numeric variable or parameter, a numeric function (`TO_NUMBER`, `ABS`, `ROUND`, ...), an expression with `*` or `/`, or a second argument that is a number - a date's is a format string. `TRUNC` of a column cannot be told apart and is not flagged.

Implemented: `ora2pg_gap_report/detectors/trunc_number.py`.
