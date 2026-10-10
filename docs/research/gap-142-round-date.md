# GAP-142: `ROUND` of a date

Oracle feature: `ROUND(d[, fmt])` rounds a date - to the nearest day, or by a format such as `'MM'`.

## How it was found

While checking the earlier gaps: the same functions were run in Oracle 23ai and, after ora2pg 25.0, in PostgreSQL 16.

## Minimal example

`tests/fixtures/char_to_char_round/oracle_functions.sql`, VALID in a live Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_r4(d DATE) RETURN VARCHAR2 IS
BEGIN
  RETURN TO_CHAR(ROUND(d, 'MM'), 'YYYY-MM-DD') || '|' || TO_CHAR(ROUND(d), 'YYYY-MM-DD');
END;
/
```

## ora2pg output (v25.0)

```sql
  RETURN TO_CHAR(ROUND(d, 'MM'), 'YYYY-MM-DD') || '|' || TO_CHAR(ROUND(d), 'YYYY-MM-DD');
```

ora2pg rewrites `TRUNC(d, 'MM')` into `date_trunc('month', d)` (checked: `'MM'`, `'IW'`, `'Q'` come out right) but copies `ROUND`.

## Observed problem

The function loads; the call fails (Oracle 23ai, for 2026-03-17 15:00: `2026-04-01|2026-03-18`):

```
ERROR:  function round(timestamp without time zone, unknown) does not exist
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** Rewrite it with `date_trunc`: `date_trunc('day', d + interval '12 hours')` for a day; for a month, compare the day of the month with 16. The detector flags `ROUND` with a string second argument (only a date's `ROUND` takes a format), and `ROUND` of a `DATE`/`TIMESTAMP` variable or of `SYSDATE`.

Implemented: `ora2pg_gap_report/detectors/round_date.py`.
