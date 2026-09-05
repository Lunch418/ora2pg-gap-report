# GAP-092: `IF` is not completed into PL/pgSQL form

MSSQL feature: `IF` — the T-SQL conditional statement, in two forms: with
a `BEGIN ... END` block and without one.

## Minimal example

```sql
CREATE PROCEDURE dbo.if_blk @x int AS
BEGIN
    IF @x < 0
    BEGIN
        INSERT INTO orders (nm) VALUES ('neg');
    END
END;
```

## ora2pg output (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.if_blk (p_x integer) AS $body$
BEGIN
BEGIN 
     IF  p_x < 0 THEN
        INSERT INTO orders(nm) VALUES ('neg');
    END
END;
END;
$body$
```

The `THEN` keyword is inserted correctly, but the closing `END` stayed
`END` instead of `END IF`.

## Observed problem

The load goes through cleanly — ora2pg sets `check_function_bodies =
false` in its own output, so the body is not parsed. When the body is
parsed on a real PostgreSQL 16:

```
ERROR:  syntax error at or near "END"
```

The second form, without a block, breaks differently — there `THEN` is
not inserted either:

```sql
CREATE PROCEDURE dbo.if_nb @x int AS
BEGIN
    IF @x < 0
        INSERT INTO orders (nm) VALUES ('neg');
END;
```

```
ERROR:  missing "THEN" at end of SQL expression
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** Both forms are
broken, but in different ways, so the detector deliberately makes no
attempt to distinguish them: the fix is the same either way — rewriting
into the full PL/pgSQL form, `IF <condition> THEN <statements>; END IF;`.
Implemented: `ora2pg_gap_report/detectors/mssql_if_statement.py`.
