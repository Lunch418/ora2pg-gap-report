# GAP-093: `RAISERROR` / `THROW` are copied as-is

MSSQL feature: `RAISERROR` and `THROW` — the T-SQL error-raising
statements.

## Minimal example

```sql
CREATE PROCEDURE dbo.check_amt @amt int AS
BEGIN
    IF @amt < 0
        RAISERROR ('amount must be positive', 16, 1);
END;
```

## ora2pg output (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.check_amt (p_amt integer) AS $body$
BEGIN
BEGIN 
     IF  p_amt < 0
        RAISERROR('amount must be positive', 16, 1);
END;
END;
$body$
```

The statement is copied verbatim. The same happens with `THROW 50001,
'amount must be positive', 1;`.

## Observed problem

The load goes through cleanly — ora2pg sets `check_function_bodies =
false` in its own output, so the body is not parsed. When the body is
parsed on a real PostgreSQL 16:

```
ERROR:  missing "THEN" at end of SQL expression
LINE 5:         RAISERROR('amount must be positive', 16, 1);
```

(in this example the neighbouring GAP-092 on `IF` fires first;
`RAISERROR` itself does not exist in PL/pgSQL regardless)

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** Rewritten to
`RAISE EXCEPTION '<text>' USING ERRCODE = '<sqlstate>'`. Two things to
keep in mind when porting: the severity in `RAISERROR` (the second
argument) corresponds in PostgreSQL not to an error code but to the
message level (`RAISE NOTICE`/`WARNING`/`EXCEPTION`), and error numbers
from `THROW` (>= 50000) have to be mapped to five-character SQLSTATEs by
hand. Implemented: `ora2pg_gap_report/detectors/mssql_raiserror.py`.
