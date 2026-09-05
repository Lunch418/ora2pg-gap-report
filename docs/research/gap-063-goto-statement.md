# GAP-063: the `GOTO` statement

Oracle feature: an unconditional jump to a `<<label>>` inside a PL/SQL
block.

## Minimal example

```sql
CREATE OR REPLACE PROCEDURE hop IS
  i NUMBER := 0;
BEGIN
  <<again>>
  i := i + 1;
  IF i < 3 THEN
    GOTO again;
  END IF;
END;
/
```

## ora2pg output (v25.0, `-t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE hop () AS $body$
DECLARE
  i bigint := 0;
BEGIN
  <<again>>
  i := i + 1;
  IF i < 3 THEN
    GOTO again;
  END IF;
END;
$body$
LANGUAGE PLPGSQL
;
```

Both the label and the `GOTO` are copied as written.

## Observed problem

The load succeeds cleanly (`check_function_bodies = false`):

```
CREATE PROCEDURE
```

The failure comes on the first call. Confirmed against a real PostgreSQL
16:

```
ERROR:  syntax error at or near "i"
LINE 8:   i := i + 1;
          ^
```

PL/pgSQL has no `GOTO` statement at all. The label `<<again>>` is by
itself syntactically valid (PL/pgSQL labels blocks and loops), so the
parse stumbles on the line after it.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/goto_statement.py`. Manual rework: rewrite it
with control structures — a backward jump becomes a `LOOP`/`CONTINUE`, and
a forward jump over a piece of code becomes an `IF`/`ELSE` or that piece
being moved into a nested block with an `EXIT`.
