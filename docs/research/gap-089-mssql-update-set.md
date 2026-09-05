# GAP-089: `UPDATE ... SET` turns into a `:=` assignment

MSSQL feature: an ordinary `UPDATE ... SET` — nothing exotic, just the
most common statement in stored procedures.

## Minimal example

```sql
CREATE PROCEDURE dbo.upd_only @x int AS
BEGIN
    UPDATE orders SET amount = @x, nm = 'y' WHERE id = 1;
END;
```

## ora2pg output (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.upd_only (p_x integer) AS $body$
BEGIN
BEGIN 
     UPDATE  orders amount := p_x, nm = 'y' WHERE id = 1;
END;
END;
$body$
LANGUAGE PLPGSQL
;
```

The `SET` keyword vanished from the statement, and the first assignment
got `:=` instead of `=`. The cause is clear: in T-SQL `SET` is also the
variable-assignment statement (`SET @x = 1`), and ora2pg applied the
assignment rules to the query.

## Observed problem

The load goes through cleanly — ora2pg sets `check_function_bodies =
false` in its own output, so the body is not parsed. When the body is
parsed on a real PostgreSQL 16:

```
ERROR:  syntax error at or near ":="
```

Checked on three different procedures — with a parameter, without a
parameter, and with an `IF` block: `UPDATE` breaks in all of them.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** This catches
every `UPDATE` in every procedure, so after conversion they all have to
be reviewed. Fixed by restoring plain SQL: `UPDATE <table> SET <column> =
<value>`. Implemented:
`ora2pg_gap_report/detectors/mssql_update_set.py` — the detector
deliberately does not flag a genuine T-SQL variable assignment (`SET @x =
1`), which ora2pg translates correctly.
