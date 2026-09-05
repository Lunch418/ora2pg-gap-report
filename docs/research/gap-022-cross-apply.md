# GAP-022: `CROSS APPLY` / `OUTER APPLY` — PostgreSQL has no APPLY syntax

Oracle feature (12c+): `CROSS APPLY`/`OUTER APPLY` — invoking a table
subexpression for each row of the outer query, with access to that row's
columns (the equivalent of `LATERAL JOIN` in other databases).

## Minimal example

```sql
SELECT COUNT(*) INTO v_count
FROM customers c
CROSS APPLY (
    SELECT o.order_id, o.amount
    FROM orders o
    WHERE o.customer_id = c.customer_id
    ORDER BY o.order_date DESC
    FETCH FIRST 1 ROWS ONLY
) latest;
```

## ora2pg output (v25.0, `-t PACKAGE`)

`CROSS APPLY(...)` is copied as written (the space before the parenthesis
is removed, but that is cosmetic — the construct itself is untouched).

## Observed problem

Confirmed against a real PostgreSQL 16: `CREATE PROCEDURE` succeeds
without error and fails on the first call:

```
ERROR:  syntax error at or near "APPLY"
LINE 2:         CROSS APPLY(
```

PostgreSQL has no `APPLY` syntax at all. The nearest architectural
equivalent is `JOIN LATERAL (...) ON true` (for `CROSS APPLY`) or `LEFT
JOIN LATERAL (...) ON true` (for `OUTER APPLY`) — syntactically similar,
but every occurrence has to be edited by hand.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/cross_apply.py`.
