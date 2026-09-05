# GAP-013: `PARTITION BY RANGE/LIST/HASH/REFERENCE/SYSTEM` — table partitioning dropped entirely

Oracle feature: declarative table partitioning (`PARTITION BY
RANGE/LIST/HASH/REFERENCE/SYSTEM (...)`) — an architectural strategy for
storing and maintaining large tables (partition pruning, per-partition
maintenance). Checked against all five strategies — ora2pg behaves the
same way for each.

## Minimal example

```sql
CREATE TABLE sales (
    sale_date DATE,
    amount    NUMBER
)
PARTITION BY RANGE (sale_date) (
    PARTITION p1 VALUES LESS THAN (DATE '2020-01-01'),
    PARTITION p2 VALUES LESS THAN (MAXVALUE)
);
```

## ora2pg output (v25.0, `-t TABLE`, and separately `--estimate_cost -t TABLE`)

```sql
CREATE TABLE sales (
    sale_date date,
    amount    numeric
);
```

`PARTITION BY` and every partition (`p1`, `p2`) vanish from the output
completely — the table is created as an ordinary, unpartitioned one. No
error, no warning — including from `--estimate_cost`, which likewise
records nothing about this table.

## Observed problem

Confirmed against a real PostgreSQL 16: the generated `CREATE TABLE` runs
without a single error — a valid table, just a different one.

For small tables that may be harmless, but for the tables partitioning was
applied to in the first place (large ones, for partition pruning or
per-partition maintenance) it is a silent loss of an architectural
decision — with no signal about it anywhere in ora2pg's output.
PostgreSQL does support declarative partitioning, but with different
syntax (`CREATE TABLE ... PARTITION OF ... FOR VALUES ...`) — the
partitions have to be recreated by hand.

Checked separately against collision cases, so this construct is not
confused with similar-looking syntax:
- **Partitioned outer join** (`table_alias PARTITION BY (col) RIGHT OUTER
  JOIN ...`) — not flagged; there is no `RANGE`/`LIST`/`HASH` there.
- **Window function** (`SUM(...) OVER (PARTITION BY col ...)`) — not
  flagged; likewise no `RANGE`/`LIST`/`HASH` right after `PARTITION BY`.
- **Partitioned index** (`CREATE INDEX ... GLOBAL PARTITION BY RANGE (col)
  (...)`) — valid Oracle syntax, but separate from table partitioning. The
  search for `PARTITION BY` is confined strictly to the text of one
  `CREATE TABLE` (up to its terminating `;`) rather than "the nearest
  preceding table in the file" — otherwise a partitioned index could be
  wrongly attributed to some unrelated table earlier in the file (found in
  code review, fixed before merge).

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/table_partitioning.py`. It requires
`PARTITION BY (RANGE|LIST|HASH)\s*\(` — the opening parenthesis right
after the keyword is precisely what distinguishes real table partitioning
from a partitioned outer join or a window function.
