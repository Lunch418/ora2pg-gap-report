# GAP-012: `CREATE GLOBAL TEMPORARY TABLE` — the lost `ON COMMIT`

Oracle feature: `CREATE GLOBAL TEMPORARY TABLE ... ON COMMIT DELETE ROWS`
(or the same semantics by default, when `ON COMMIT` is not given at all) —
the temporary table's rows are cleared after every `COMMIT`.

## Minimal example

```sql
CREATE GLOBAL TEMPORARY TABLE staging_orders (
    order_id NUMBER
) ON COMMIT DELETE ROWS;
```

(the same result with no `ON COMMIT` at all — that is Oracle's default
behaviour).

## ora2pg output (v25.0, `-t TABLE`)

```sql
CREATE TEMPORARY TABLE staging_orders (
    order_id numeric
);
```

The `ON COMMIT` clause disappears entirely — neither `DELETE ROWS` nor any
equivalent of it reaches the output. No error, no warning.

## Observed problem

This is not a syntax error — the generated SQL is valid and runs without
trouble. The problem is that an ordinary `CREATE TEMPORARY TABLE` in
PostgreSQL defaults to `ON COMMIT PRESERVE ROWS`, the exact opposite of
Oracle's default (`DELETE ROWS`).

Confirmed against a real PostgreSQL 16 in a single `psql` session:

```sql
CREATE TEMPORARY TABLE staging_orders (order_id numeric);
BEGIN;
INSERT INTO staging_orders VALUES (1);
COMMIT;
SELECT * FROM staging_orders;  -- row (1) is NOT deleted, although in
                                -- Oracle the table would be empty by now
```

The row `order_id = 1` survived the `COMMIT`, although under Oracle
semantics — and under the developer's original intent, since they used a
GTT without an explicit `PRESERVE ROWS` — it should have disappeared. This
is a silent change of behaviour: the code compiles and runs without a
single error, but starts behaving differently than it did on Oracle.

Checked separately: when the Oracle code states `ON COMMIT PRESERVE ROWS`
explicitly, the conversion is correct — that matches PostgreSQL's own
default and the behaviour does not change.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/global_temp_table.py`. Both an explicit `ON
COMMIT DELETE ROWS` and the complete absence of an `ON COMMIT` clause are
flagged, since both mean the same Oracle semantics that ora2pg loses. `ON
COMMIT PRESERVE ROWS` is not flagged — that case converts correctly.
