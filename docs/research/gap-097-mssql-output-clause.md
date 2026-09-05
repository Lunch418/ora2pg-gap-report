# GAP-097: `OUTPUT INSERTED.*` is copied as-is

MSSQL feature: `OUTPUT INSERTED.<column>` / `OUTPUT DELETED.<column>` —
returning the affected rows straight from a DML statement in T-SQL.

## Minimal example

```sql
CREATE PROCEDURE dbo.with_output AS
BEGIN
    INSERT INTO orders (nm) OUTPUT INSERTED.id VALUES ('x');
END;
```

## ora2pg output (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.with_output () AS $body$
DECLARE

;
BEGIN
BEGIN 
     INSERT  INTO orders(nm) OUTPUT INSERTED.id VALUES ('x');
END;
END;
$body$
```

The clause is copied verbatim.

## Observed problem

In PostgreSQL the same idea is written as `RETURNING`; it does not
understand the word `OUTPUT`. The load goes through cleanly
(`check_function_bodies = false` in ora2pg's output); the failure comes
on the first call.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** Rewritten to
`RETURNING <column>`, with two caveats: `RETURNING` does not distinguish
`INSERTED` from `DELETED` (for an `UPDATE` it returns the new values —
the old ones have to be obtained some other way), and unlike `OUTPUT ...
INTO <table>` its result cannot be directed into a table in a single
statement. Implemented:
`ora2pg_gap_report/detectors/mssql_output_clause.py`.
