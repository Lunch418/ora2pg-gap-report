# GAP-019: `SQL_MACRO` — a macro function converted into an ordinary function

Oracle feature: `SQL_MACRO` (Oracle 20c+) — a function modifier that turns
the function into a textual macro which Oracle substitutes directly into
the SQL statement at parse time (`SQL_MACRO(SCALAR)` as an expression,
`SQL_MACRO(TABLE)` as a table expression), rather than calling it as an
ordinary value-returning function.

## Minimal example

```sql
CREATE OR REPLACE PACKAGE BODY region_pkg AS
    FUNCTION in_top_region(p_region VARCHAR2) RETURN VARCHAR2 SQL_MACRO IS
    BEGIN
        RETURN 'region IN (''EU'', ''US'')';
    END;

    PROCEDURE count_top IS
        v_count NUMBER;
    BEGIN
        SELECT COUNT(*) INTO v_count
        FROM orders
        WHERE in_top_region(region);
    END count_top;
END region_pkg;
/
```

## ora2pg output (v25.0, `-t PACKAGE`)

`SQL_MACRO` vanishes from the function signature without trace — the
function is converted into an ordinary PL/pgSQL function returning
`varchar`. The calling code (`WHERE in_top_region(region)`) is copied as
written, with no substitution of the macro's text.

## Observed problem

Confirmed against a real PostgreSQL 16: the function itself compiles
without errors. The calling procedure fails on its first call:

```
ERROR:  argument of WHERE must be type boolean, not type character varying
LINE 2:         WHERE region_pkg_in_top_region(region)
                      ^
```

On Oracle a `SQL_MACRO(SCALAR)` function used in `WHERE` substitutes its
textual result into the query itself at parse time (`WHERE region IN ('EU',
'US')`), so it works as a boolean condition. In PostgreSQL it is just a
call to an ordinary function returning `varchar`, and PostgreSQL tries to
use that string directly as a `boolean` — a type mismatch.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/sql_macro.py`.
