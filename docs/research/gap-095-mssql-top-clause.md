# GAP-095: `SELECT TOP n` is copied as-is

MSSQL feature: `SELECT TOP <n>` — the T-SQL row-count limit.

## Minimal example

```sql
CREATE PROCEDURE dbo.topn @n int AS
BEGIN
    SELECT TOP 10 id FROM orders;
END;
```

## ora2pg output (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.topn (p_n integer) AS $body$
BEGIN
BEGIN 
     SELECT  TOP 10 id FROM orders;
END;
END;
$body$
```

Copied verbatim.

## Observed problem

The load goes through cleanly — ora2pg sets `check_function_bodies =
false` in its own output, so the body is not parsed. When the body is
parsed on a real PostgreSQL 16:

```
ERROR:  syntax error at or near "10"
LINE 4:      SELECT  TOP 10 id FROM orders;
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** Rewritten to
`LIMIT <n>` at the end of the query. `TOP` without `ORDER BY` is worth
checking separately: it is written that way often in T-SQL, and after the
move to `LIMIT` the row order remains just as undefined — if anything
relied on it, an explicit `ORDER BY` is needed. The `TOP (<n>) PERCENT`
form has no direct counterpart at all. Implemented:
`ora2pg_gap_report/detectors/mssql_top_clause.py`.
