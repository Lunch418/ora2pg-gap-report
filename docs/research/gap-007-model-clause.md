# GAP-007: the `MODEL` clause

Oracle feature: `SELECT ... MODEL PARTITION BY (...) DIMENSION BY (...)
MEASURES (...) RULES (...)` — spreadsheet-style computation inside SQL
(forecasts, running calculations). Rarer than the other gaps in this
project — mostly in financial reporting and analytics — but where it does
appear it is usually central to the logic rather than peripheral.

## Minimal example

```sql
SELECT product_id, quarter, sales
FROM sales_history
MODEL
  PARTITION BY (product_id)
  DIMENSION BY (quarter)
  MEASURES (sales)
  RULES (
    sales[4] = sales[3] * 1.1
  );
```

## ora2pg output (v25.0, `-t PACKAGE`)

The construct is left entirely untouched — `MODEL`/`PARTITION
BY`/`DIMENSION BY`/`MEASURES`/`RULES` are all copied as written.

## Observed problem

Confirmed against a real PostgreSQL 16: `CREATE PROCEDURE` succeeds
without error and fails on the first call:

```
ERROR:  syntax error at or near "PARTITION"
```

Unlike most of the project's other gaps, `MODEL` has **no direct
architectural equivalent** in PostgreSQL at all — not through an extension,
not through a syntactic substitution. The only path is rewriting the logic
with window functions (`LAG`/`LEAD`/`SUM() OVER (...)`) or recursive CTEs,
which requires understanding what the `RULES` mean for the business rather
than a mechanical substitution.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Encountered less often in practice than the project's
other detectors, but unambiguous and architecturally the heaviest — there
is no automatic conversion path even in principle, only a manual redesign
of the query.

Implemented in `ora2pg_gap_report/detectors/model_clause.py`.
