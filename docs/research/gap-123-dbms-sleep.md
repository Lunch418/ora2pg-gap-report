# GAP-123: `DBMS_LOCK.SLEEP` becomes `pg_sleep(n);` without `PERFORM`

Oracle feature: `DBMS_LOCK.SLEEP(n)` or, since 18c, `DBMS_SESSION.SLEEP(n)`
called as a statement.

## How it was found

Reducing GAP-122: the first error in the minimal case was not the
supplied package call but the line ora2pg had converted.

## Minimal example

`tests/fixtures/gaps_120_123/edge_source.sql`:

```sql
    SYS.DBMS_SESSION.SLEEP(0.1);
    IF c IS NULL THEN DBMS_SESSION.SLEEP(1); END IF;
```

in a package procedure, and `DBMS_SESSION.SLEEP(0);` in a trigger. VALID
in a live Oracle 23ai.

## ora2pg output (v25.0, `-t PACKAGE`, `-t TRIGGER`)

```sql
    pg_sleep(0.1);
    IF c IS NULL THEN pg_sleep(1);END IF;
```

ora2pg's `Ora2Pg/PLSQL.pm` has two rules for the call. `plsql_to_plpgsql`
writes `PERFORM pg_sleep`; `replace_oracle_function` writes a bare
`pg_sleep` - and runs first, so the PERFORM rule never sees
`DBMS_LOCK.SLEEP`.

## Observed problem

PL/pgSQL does not take a function called as a statement without
`PERFORM`:

```
ERROR:  42601: syntax error at or near "pg_sleep"
```

and the routine or trigger function does not load.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Mechanical:
`PERFORM pg_sleep(n);`. `--fix` does it (`fix_bare_pg_sleep` in
`ora2pg_gap_report/autofix.py`), and `--load-check` reports the error as
fixable. `--migrate` applies it.

Implemented: `ora2pg_gap_report/detectors/dbms_sleep.py`.
