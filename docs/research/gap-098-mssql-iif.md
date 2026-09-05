# GAP-098: `IIF()` is copied as-is

MSSQL feature: `IIF(<condition>, <if true>, <if false>)` — the T-SQL
ternary choice.

## Minimal example

```sql
CREATE PROCEDURE dbo.use_iif AS
BEGIN
    SELECT IIF(amount > 0, 'pos', 'neg'), CHARINDEX('a', nm) FROM orders;
END;
```

## ora2pg output (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.use_iif () AS $body$
DECLARE

;
BEGIN
BEGIN 
     SELECT  IIF(amount > 0, 'pos', 'neg'), position(''a'' in nm) FROM orders;
END;
END;
$body$
```

`IIF` is copied verbatim. Tellingly, ora2pg does try to translate the
neighbouring `CHARINDEX` in the same statement (and gets it wrong — see
GAP-100), so `IIF` is simply absent from its mapping table.

## Observed problem

PostgreSQL has no `IIF` function, and the procedure fails on the very
first real call. The load goes through cleanly — ora2pg sets
`check_function_bodies = false` in its own output.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** Rewritten to
`CASE WHEN <condition> THEN <if true> ELSE <if false> END`. Implemented:
`ora2pg_gap_report/detectors/mssql_iif.py`.
