# GAP-096: `SCOPE_IDENTITY()` / `@@IDENTITY` are copied as-is

MSSQL feature: `SCOPE_IDENTITY()`, `@@IDENTITY`, `IDENT_CURRENT()` — the
ways to obtain the value `IDENTITY` produced on the most recent insert.

## Minimal example

```sql
CREATE PROCEDURE dbo.add_row AS
BEGIN
    INSERT INTO orders (name) VALUES ('x');
    SELECT SCOPE_IDENTITY();
END;
```

## ora2pg output (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.add_row () AS $body$
DECLARE

;
BEGIN
BEGIN 
     INSERT  INTO orders(name) VALUES ('x');
    SELECT SCOPE_IDENTITY();
END;
END;
$body$
```

The call is copied verbatim.

## Observed problem

PostgreSQL has neither such a function nor such a system variable — the
procedure fails on the very first real call. The load goes through
cleanly (`check_function_bodies = false` in ora2pg's output).

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** Best rewritten
to `INSERT ... RETURNING <column> INTO <variable>`. Note that the
`IDENTITY` column itself is lost as well (GAP-090), so there may be
nothing left to return — the two places are fixed together. Implemented:
`ora2pg_gap_report/detectors/mssql_scope_identity.py`.
