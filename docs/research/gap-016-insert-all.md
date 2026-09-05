# GAP-016: `INSERT ALL` / `INSERT FIRST` — multi-table insert

Oracle feature: `INSERT ALL`/`INSERT FIRST` — a multi-table insert, either
conditional (`WHEN ... THEN INTO ...`) or unconditional (several `INTO`
clauses in a row with no `WHEN`), distributing the source rows across
several target tables in one statement.

## Minimal example

```sql
CREATE OR REPLACE PROCEDURE split_orders AS
BEGIN
    INSERT ALL
        WHEN amount > 1000 THEN
            INTO big_orders (order_id, amount)
            VALUES (order_id, amount)
        WHEN amount <= 1000 THEN
            INTO small_orders (order_id, amount)
            VALUES (order_id, amount)
    SELECT order_id, amount FROM staging_orders;
END;
/
```

## ora2pg output (v25.0, `-t PACKAGE`)

The construct is copied as written, with no change at all — neither
`INSERT ALL` nor the `INTO`/`WHEN` clauses are rewritten.

## Observed problem

Confirmed against a real PostgreSQL 16: `CREATE PROCEDURE` succeeds without
error (`check_function_bodies = false`), but fails at the body's
compilation stage on the first `CALL`:

```
ERROR:  "big_orders" is not a known variable
LINE 5:                 INTO big_orders(order_id, amount)
                             ^
```

PL/pgSQL reads `INTO table` as a form of `SELECT ... INTO variable` — the
construct used to assign a query result to a PL/pgSQL variable — rather
than as a branch of a multi-table insert. PostgreSQL has no multi-table
`INSERT` syntax at all.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/insert_all.py`. Both `INSERT ALL` and `INSERT
FIRST` are flagged, including the unconditional variant with no `WHEN` —
the only requirement is an `INTO` within a reasonable window after the
keyword, which holds for any real multi-table `INSERT`.
