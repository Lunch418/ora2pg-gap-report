# GAP-025: an `INVISIBLE` index loses its invisibility to the optimizer

Oracle feature: `INVISIBLE` — an index modifier that makes Oracle's
optimizer ignore the index by default (until a session explicitly sets
`OPTIMIZER_USE_INVISIBLE_INDEXES=TRUE`), while still maintaining its data
on DML. The typical use is to add an index invisibly, check the load and
the plans, and then make it `VISIBLE`. Not the same thing as an
`INVISIBLE` column (see GAP-020) — different objects, different kind of
risk.

## Minimal example

```sql
CREATE TABLE orders (
    order_id NUMBER,
    status   VARCHAR2(20)
);

CREATE INDEX orders_status_idx ON orders(status) INVISIBLE;
```

## ora2pg output (v25.0, `-t TABLE`)

```sql
CREATE INDEX orders_status_idx ON orders (status);
```

The `INVISIBLE` modifier disappears without trace.

## Observed problem

Not a syntax error — the `CREATE INDEX` runs without trouble. PostgreSQL
has no analogue of `INVISIBLE` for indexes at all, so the behaviour
changes silently: PostgreSQL's optimizer starts considering the index in
execution plans immediately, whereas on Oracle it would have been excluded
by default. For the "added it invisibly to check the load before
activating" scenario this is exactly the opposite effect — the index is
live at once.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/invisible_index.py`. Severity `medium` —
unlike GAP-013/GAP-018 (`table_partitioning`/`external_table`, also "the
construct silently disappears and PostgreSQL raises no error", but
`high`), the worst realistic outcome here is a suboptimal execution plan,
not data loss or architectural degradation (partitioning, or a table's
data source). For GAP-013/GAP-018 "silently disappears" means the table
physically stores or finds its data differently; here it means the
optimizer considers one more index than intended. Different levels of real
risk behind the same "no error from PostgreSQL".
