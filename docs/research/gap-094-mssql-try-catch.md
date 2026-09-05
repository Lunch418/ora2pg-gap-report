# GAP-094: `BEGIN TRY` / `BEGIN CATCH` are copied as-is

MSSQL feature: `BEGIN TRY ... END TRY BEGIN CATCH ... END CATCH` — error
handling in T-SQL.

## Minimal example

```sql
CREATE PROCEDURE dbo.safe_op AS
BEGIN
    BEGIN TRY
        INSERT INTO t1 (id) VALUES (1);
    END TRY
    BEGIN CATCH
        SELECT ERROR_MESSAGE();
    END CATCH
END;
```

## ora2pg output (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.safe_op () AS $body$
DECLARE

;
BEGIN
BEGIN 
     BEGIN  TRY
        INSERT INTO t1(id) VALUES (1);
    END TRY
    BEGIN CATCH
        SELECT ERROR_MESSAGE();
    END CATCH
END;
END;
$body$
```

The whole construct is copied verbatim, `END TRY` and `END CATCH`
included.

## Observed problem

The load goes through cleanly — ora2pg sets `check_function_bodies =
false` in its own output, so the body is not parsed. When the body is
parsed on a real PostgreSQL 16:

```
ERROR:  syntax error at or near ";"
```

(in this example GAP-091 fires first — a parameterless procedure;
`BEGIN TRY` itself does not exist in PL/pgSQL regardless)

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** Rewritten into
a `BEGIN ... EXCEPTION WHEN OTHERS THEN ... END` block, and the calls
inside the `CATCH` change too: `ERROR_MESSAGE()` becomes `SQLERRM`,
`ERROR_NUMBER()` becomes `SQLSTATE`. Implemented:
`ora2pg_gap_report/detectors/mssql_try_catch.py`.
