# GAP-034: a local nested procedure/function loses its structure on export

Oracle feature: a procedure or function declared locally inside another
block's declarative section (a package, procedure, function, or anonymous
block) — before the containing block's `BEGIN`. The usual way to factor
out helper logic needed only inside one procedure, without making it a
separate package member.

## Minimal example

```sql
CREATE OR REPLACE PROCEDURE outer_proc AS
  PROCEDURE inner_proc(p_val NUMBER) IS
  BEGIN
    DBMS_OUTPUT.PUT_LINE('inner: ' || p_val);
  END;
BEGIN
  inner_proc(42);
END;
```

## ora2pg output (v25.0, `-t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE inner_proc (p_val bigint) AS $body$
BEGIN
    RAISE NOTICE 'inner: %', p_val;
  END;
BEGIN
  CALL inner_proc(42);
END;
$body$
LANGUAGE PLPGSQL
;
```

The nested `inner_proc` leaks out as a separate top-level procedure —
`outer_proc` does not exist in the output at all. Worse, `inner_proc`'s
body in the output is mangled: after its own `END;` — with no terminating
semicolon to close it off — comes `BEGIN CALL inner_proc(42); END;`, which
should have been `outer_proc`'s executable body, all of it glued inside
`inner_proc`'s body as a single block.

## Observed problem

The `CREATE PROCEDURE` in the output runs without a single error — ora2pg
disables `check_function_bodies` at the very start of the generated file,
so the body's syntax is not checked at `CREATE` time. The failure happens
only on the first real call, at the body's compilation stage:

```sql
CALL inner_proc(1);
-- ERROR:  syntax error at or near "BEGIN"
-- LINE 5: BEGIN
-- CONTEXT:  compilation of PL/pgSQL function "inner_proc" near line 2
```

Exactly the same pattern as `$IF`/`$THEN` (GAP-035): the migration script
applies cleanly all the way through, every object appears to have been
created, and the broken code is discovered only when a call actually
reaches it — which may happen in production rather than in testing. On top
of that, the original procedure (`outer_proc`) vanishes from the output
entirely without a warning: what is lost is not only the nested function
but also whatever called it.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/nested_subprogram.py`.
