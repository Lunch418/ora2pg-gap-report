# GAP-008: `PIVOT`/`UNPIVOT`

Oracle feature: `PIVOT (aggregate_function FOR pivot_column IN (values))` /
`UNPIVOT (...)` — turning rows into columns and back directly in SQL,
without writing conditional aggregation by hand. Common in reporting.

## Minimal example

```sql
SELECT * FROM (SELECT product_id, quarter, sales FROM sales_history)
PIVOT (
  SUM(sales)
  FOR quarter IN ('Q1' AS q1, 'Q2' AS q2, 'Q3' AS q3, 'Q4' AS q4)
);
```

## ora2pg output (v25.0, `-t PACKAGE`)

The construct is copied as written, with no change at all beyond the
cosmetic removal of a space before a parenthesis.

## Observed problem

Confirmed against a real PostgreSQL 16: `CREATE PROCEDURE` succeeds
without error and fails on the first call:

```
ERROR:  syntax error at or near "("
LINE 4:         SUM(sales)
```

PostgreSQL has no built-in `PIVOT`/`UNPIVOT` at all. The usual rewrite is
conditional aggregation (`FILTER (WHERE ...)`/`CASE WHEN`) or the
`tablefunc` extension (`crosstab()`) — architecturally different
approaches, depending on whether the list of values to pivot on is known
in advance.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/pivot_clause.py`.
