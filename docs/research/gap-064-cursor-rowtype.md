# GAP-064: `<cursor>%ROWTYPE`

Oracle feature: declaring a variable with a cursor's structure.

## Minimal example

```sql
CREATE OR REPLACE PROCEDURE walk IS
  CURSOR c IS SELECT emp_id, name FROM employees;
  r c%ROWTYPE;
BEGIN
  OPEN c; FETCH c INTO r; CLOSE c;
END;
/
```

## ora2pg output (v25.0, `-t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE walk () AS $body$
DECLARE
  c CURSOR FOR SELECT emp_id, name FROM employees;
  r c%ROWTYPE;
BEGIN
  OPEN c;FETCH c INTO r;CLOSE c;
END;
$body$
LANGUAGE PLPGSQL
;
```

The cursor's own declaration is rewritten correctly (`CURSOR c IS` → `c
CURSOR FOR`), while `c%ROWTYPE` is left as written.

## Observed problem

The load succeeds cleanly (`check_function_bodies = false`):

```
CREATE PROCEDURE
```

The failure comes on the first call. Confirmed against a real PostgreSQL
16:

```
ERROR:  relation "c" does not exist
CONTEXT:  compilation of PL/pgSQL function "walk" near line 5
```

PL/pgSQL understands `%ROWTYPE` only from a table or a view, not from a
cursor, so the cursor's name is taken for a relation name.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/cursor_rowtype.py`. The detector flags
`%ROWTYPE` only from a name declared as a `CURSOR` in the same file: an
ordinary `<table>%ROWTYPE` is carried over correctly by ora2pg, and
flagging it would be a false positive.

Manual rework: declare the variable as `RECORD` — in PL/pgSQL a variable
of that type accepts a row from any cursor, and `FETCH` into it works
unchanged.
