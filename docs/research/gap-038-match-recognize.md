# GAP-038: `MATCH_RECOGNIZE` — row pattern matching

Oracle feature: `MATCH_RECOGNIZE` (12c+) — finding sequences of rows that
match a regular-expression-like pattern, directly in SQL: partitioning,
ordering, declaring pattern variables (`DEFINE`), and computing values
from a match (`MEASURES`).

## Minimal example

```sql
CREATE OR REPLACE VIEW v_price_runs AS
SELECT *
FROM ticker_prices
MATCH_RECOGNIZE (
  PARTITION BY symbol
  ORDER BY price_date
  MEASURES STRT.price_date AS start_date,
           LAST(UP.price_date) AS end_date
  ONE ROW PER MATCH
  PATTERN (STRT UP+)
  DEFINE UP AS UP.price > PREV(UP.price)
);
```

## ora2pg output (v25.0, `-t VIEW`)

```sql
CREATE OR REPLACE VIEW v_price_runs AS SELECT *
FROM ticker_prices
MATCH_RECOGNIZE(
  PARTITION BY symbol
  ORDER BY price_date
  MEASURES STRT.price_date AS start_date,
           LAST(UP.price_date) AS end_date
  ONE ROW PER MATCH
  PATTERN(STRT UP+)
  DEFINE UP AS UP.price > PREV(UP.price)
);
```

The construct is copied into the output as written — ora2pg neither tries
to convert it nor warns about it.

## Observed problem

Confirmed against a real PostgreSQL 16 — it fails while loading the
generated DDL:

```
ERROR:  syntax error at or near "BY"
LINE 4:   PARTITION BY symbol
                    ^
```

PostgreSQL has no row pattern matching in any form — neither in the syntax
nor through an extension out of the box.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/match_recognize.py`. Manual rework: window
functions (`LAG`/`LEAD` over the partition) followed by filtering, or a
recursive CTE — there is no single-construct replacement.
