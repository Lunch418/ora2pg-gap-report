# GAP-060: `PRAGMA EXCEPTION_INIT` — the handler becomes dead code

Oracle feature: binding a declared exception to an Oracle error number, so
it can be caught by name in `WHEN`.

## Minimal example

```sql
CREATE OR REPLACE PROCEDURE ins_one IS
  dup_key EXCEPTION;
  PRAGMA EXCEPTION_INIT(dup_key, -1);
BEGIN
  INSERT INTO uniq_t (id) VALUES (1);
EXCEPTION
  WHEN dup_key THEN
    DBMS_OUTPUT.PUT_LINE('handled duplicate');
END;
/
```

ORA-00001 is a uniqueness violation. On Oracle the procedure prints
`handled duplicate`.

## ora2pg output (v25.0, `-t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE ins_one () AS $body$
BEGIN
  INSERT INTO uniq_t(id) VALUES (1);
EXCEPTION
  WHEN SQLSTATE '50001' THEN
    RAISE NOTICE 'handled duplicate';
END;
$body$
LANGUAGE PLPGSQL
;
```

The `PRAGMA` itself is discarded and the handler rewritten to `WHEN
SQLSTATE '50001'`.

## Observed problem

`'50001'` is a constant, independent of the ORA number. Checked with two
different ones: `-1` (ORA-00001, uniqueness) and `-60` (ORA-00060,
deadlock) — in both cases the output says `SQLSTATE '50001'`.

The procedure is created without a single error:

```
CREATE PROCEDURE
```

Then comes a real call against a real unique constraint. Confirmed on
PostgreSQL 16:

```
ERROR:  duplicate key value violates unique constraint "uniq_t_pkey"
DETAIL:  Key (id)=(1) already exists.
CONTEXT:  SQL statement "INSERT INTO uniq_t(id) VALUES (1)"
PL/pgSQL function ins_one() line 3 at SQL statement
```

The handler did not fire. PostgreSQL's real code for this error is
`23505`, verified in the same session:

```
NOTICE:  unique_violation SQLSTATE = 23505
```

PostgreSQL never raises `50001`, so the handler becomes dead code, and an
error that Oracle handled escapes silently after migration and brings down
the calling code.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/pragma_exception_init.py`. Manual rework: map
each ORA number onto PostgreSQL's real code and replace `'50001'` with it
— or with a named condition such as `unique_violation` /
`deadlock_detected`, which reads better.
