# GAP-027: `CREATE MATERIALIZED VIEW LOG` is not converted at all

Oracle feature: a table's change log (`CREATE MATERIALIZED VIEW LOG ON
table ...`), required for the incremental `FAST REFRESH` of materialized
views built on that table.

## Minimal example

```sql
CREATE TABLE products (
    product_id NUMBER,
    name       VARCHAR2(100)
);

CREATE MATERIALIZED VIEW LOG ON products
WITH ROWID, SEQUENCE (product_id, name)
INCLUDING NEW VALUES;
```

## ora2pg output (v25.0, `-t TABLE`)

```
[DEBUG] unhandled line: CREATE MATERIALIZED VIEW LOG ON products
WITH ROWID, SEQUENCE (product_id, name)
INCLUDING NEW VALUES;
```

The construct disappears from the output completely — not as an
`-- Unsupported` comment, but without a trace beyond a **DEBUG**-level
line in the log.

## Observed problem

Not a syntax error — the `products` table itself is created normally, the
log simply never appears. If a materialized view with `REFRESH FAST` on
this table exists anywhere in the schema, it stops working in fast-refresh
mode without an explicit log. PostgreSQL has no incremental `REFRESH FAST`
for materialized views at all — only a full `REFRESH MATERIALIZED VIEW` —
so the concept of a change log is not needed there; but that means an
architecturally different approach to refreshing the data (a full
recomputation instead of an incremental one), which has to be designed
anew rather than carried over syntactically.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/materialized_view_log.py`. Severity `high` —
the same profile as GAP-013/GAP-018
(`table_partitioning`/`external_table`): the construct silently disappears
with no error at all from PostgreSQL, yet it means a real architectural
loss (here, the refresh strategy of dependent materialized views) rather
than mere suboptimality — compare GAP-025, which is `medium` precisely
because its risk is confined to the execution plan.
