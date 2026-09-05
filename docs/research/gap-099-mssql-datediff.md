# GAP-099: `DATEDIFF()` is copied as-is

MSSQL feature: `DATEDIFF(<unit>, <start>, <end>)` — the difference
between two dates.

## Minimal example

```sql
CREATE PROCEDURE dbo.datefns AS
BEGIN
    SELECT DATEADD(day, 7, created), DATEDIFF(day, created, GETDATE()), DATEPART(year, created) FROM orders;
END;
```

## ora2pg output (v25.0, `-M -t PROCEDURE`)

```sql
     SELECT  created + INTERVAL '7 day', DATEDIFF(day, created, date_trunc('millisecond', CURRENT_TIMESTAMP::timestamp)), date_part('year', created) FROM orders;
```

The neighbouring functions are translated correctly: `DATEADD` became
`INTERVAL` arithmetic, `DATEPART` became `date_part()`, `GETDATE()`
became a `CURRENT_TIMESTAMP` expression. `DATEDIFF` stayed as it was.

## Observed problem

PostgreSQL has no `DATEDIFF` function. The load goes through cleanly
(`check_function_bodies = false` in ora2pg's output); the failure comes
on the first real call.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** Rewritten with
subtraction: the difference in days is `(<end>::date - <start>::date)`,
other units go through `EXTRACT(EPOCH FROM (<end> - <start>))` with a
division. Mind the semantics: T-SQL's `DATEDIFF` counts crossed unit
boundaries rather than whole intervals, so `DATEDIFF(year, ...)` between
31 December and 1 January gives 1, while a direct subtraction gives 0.
Implemented: `ora2pg_gap_report/detectors/mssql_datediff.py`.
