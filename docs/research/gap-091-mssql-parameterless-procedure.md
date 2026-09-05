# GAP-091: a parameterless procedure gets an empty `DECLARE`

MSSQL feature: a stored procedure with no parameters — typically all the
housekeeping and reporting ones.

## Minimal example

```sql
CREATE PROCEDURE dbo.noparams AS
BEGIN
    UPDATE t SET a = 1;
END;
```

## ora2pg output (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.noparams () AS $body$
DECLARE

;
BEGIN
...
```

The declaration block is empty: `DECLARE`, a blank line and a lone
semicolon.

## Isolation

Verified by a direct comparison with exactly the same procedure that does
have a parameter:

```sql
CREATE PROCEDURE dbo.withparams @x int AS
BEGIN
    UPDATE t SET a = @x;
END;
```

```sql
CREATE OR REPLACE PROCEDURE dbo.withparams (p_x integer) AS $body$
BEGIN
...
```

There is no `DECLARE` block at all; the body starts straight at `BEGIN`.
So the broken `DECLARE` appears exactly when there are no parameters.

## Observed problem

The load goes through cleanly (`check_function_bodies = false` in
ora2pg's output). When the body is parsed on a real PostgreSQL 16:

```
ERROR:  syntax error at or near ";"
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** Fixed by
removing the empty `DECLARE` from the generated code (or by putting real
variables into it, if any are needed). Implemented:
`ora2pg_gap_report/detectors/mssql_parameterless_procedure.py` — the
detector flags a procedure that has no `@` parameter between its name and
`AS`.
