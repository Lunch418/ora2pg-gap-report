# GAP-010: `WITH FUNCTION`/`WITH PROCEDURE` — ora2pg's parser destroys the structure

Oracle feature (12c+): an inline function or procedure defined directly
inside a query's `WITH` clause — scoped to that query, with no separate
declaration in a package.

## Minimal example

```sql
CREATE OR REPLACE PACKAGE BODY calc_pkg AS
  PROCEDURE run_calc IS
    v_total NUMBER;
  BEGIN
    WITH
      FUNCTION apply_discount(p_amount NUMBER) RETURN NUMBER IS
      BEGIN
        RETURN p_amount * 0.9;
      END;
    SELECT SUM(apply_discount(amount)) INTO v_total FROM orders;
  END run_calc;
END calc_pkg;
/
```

## ora2pg output (v25.0, `-t PACKAGE`)

This is the project's most serious finding in character — not "the
construct isn't converted" but **the parser destroys the structure of the
source**:

```sql
CREATE OR REPLACE PROCEDURE calc_pkg_run_calc () AS $body$
DECLARE
    v_total bigint;
BEGIN
    WITH;
$body$
LANGUAGE PLPGSQL
;

CREATE OR REPLACE FUNCTION calc_pkg_apply_discount (p_amount bigint) RETURNS bigint AS $body$
BEGIN
        RETURN p_amount * 0.9;
      END;
    SELECT SUM(calc_pkg_apply_discount(amount)) INTO STRICT v_total FROM orders;
  END;
$body$
LANGUAGE PLPGSQL
;
```

The nested `apply_discount` has leaked out as a separate top-level package
function (`calc_pkg_apply_discount`), and `run_calc`'s body has been
truncated to literally `BEGIN WITH;` — the entire real query (`SELECT
SUM(...) INTO v_total FROM orders`) has physically vanished from
`run_calc`'s body and ended up glued to the end of `apply_discount`'s body
instead.

## Observed problem

Confirmed against a real PostgreSQL 16: both `CREATE` statements succeed
without error (`check_function_bodies = false`), but `run_calc` fails at
the **compilation** stage of the function body on the first call, not
merely at execution:

```
ERROR:  syntax error at end of input
CONTEXT:  compilation of PL/pgSQL function "calc_pkg_run_calc" near line 7
```

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed, and this is structural corruption of the code rather
than merely an unconverted construct.** Implemented in
`ora2pg_gap_report/detectors/with_function.py`.
