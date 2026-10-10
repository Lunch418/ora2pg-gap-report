# GAP-138: arithmetic on a `DATE` variable

Oracle feature: `date + n` is the date n days later (n may be a fraction, `1/24` is an hour), and `date - date` is a number of days.

## How it was found

While checking GAP-130..133: the same functions were run in Oracle 23ai and, after ora2pg 25.0, in PostgreSQL 16.

## Minimal example

`tests/fixtures/loud_types/oracle_functions.sql`, VALID in a live Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_l6(d1 DATE, d2 DATE) RETURN NUMBER IS
  days NUMBER;
BEGIN
  days := d1 - d2;
  RETURN days;
END;
/
CREATE OR REPLACE FUNCTION gx_l7(d DATE) RETURN VARCHAR2 IS
  nxt DATE := d + 1;
BEGIN
  RETURN TO_CHAR(nxt, 'YYYY-MM-DD') || '|' || TO_CHAR(TRUNC(d) - 7, 'YYYY-MM-DD');
END;
/
```

## ora2pg output (v25.0, `-t FUNCTION`)

```sql
  days := d1 - d2;
...
  nxt timestamp(0) := d + 1;
...
  RETURN TO_CHAR(nxt, 'YYYY-MM-DD') || '|' || TO_CHAR(date_trunc('day', d) - 7, 'YYYY-MM-DD');
```

`DATE` becomes `timestamp(0)`. `SYSDATE + 1` is rewritten as `clock_timestamp() + interval '1 days'`, but arithmetic on a variable or parameter is copied.

## Observed problem

Both load and fail when called (Oracle 23ai: `gx_l6` = 2, `gx_l7` = `2026-01-11|2026-01-03`):

```
ERROR:  invalid input syntax for type bigint: "2 days"
ERROR:  operator does not exist: timestamp without time zone + integer
```

Found in OraOpenSource Logger: eleven `p_date_stop-p_date_start` in `date_text_format_base`.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** Write `d + interval '1 day'` and `extract(epoch from (d1 - d2)) / 86400`. The detector knows the variables and parameters declared `DATE` or `TIMESTAMP` in the same routine or its package and flags a number added to or subtracted from them, `TRUNC` of them or of `SYSDATE` with a number, and the difference of two `DATE`s (`TIMESTAMP - TIMESTAMP` is an interval in Oracle too). A column's type is not known.

Implemented: `ora2pg_gap_report/detectors/date_arithmetic.py`.
