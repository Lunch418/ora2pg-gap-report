# GAP-020: an `INVISIBLE` column loses its invisibility

Oracle feature: `INVISIBLE` — a column modifier that excludes the column
from `SELECT *` and from a positional `INSERT` with no explicit column
list; the column is still available, but only when named explicitly. A
common use is adding a new column to an existing table without risking
breaking older code that relies on the previous shape of `SELECT *`.

## Minimal example

```sql
CREATE TABLE customers (
    customer_id NUMBER,
    legacy_code VARCHAR2(10) INVISIBLE
);
```

## ora2pg output (v25.0, `-t TABLE`)

```sql
CREATE TABLE customers (
	customer_id bigint,
	legacy_code varchar(10)
) ;
```

The `INVISIBLE` modifier disappears without trace — the column is
converted as an ordinary, visible one.

## Observed problem

Not a syntax error — the `CREATE TABLE` runs without trouble. PostgreSQL
has no analogue of `INVISIBLE` at all, so the behaviour changes silently.
Confirmed against a real PostgreSQL 16:

```sql
INSERT INTO customers VALUES (1, 'x');
SELECT * FROM customers;
-- customer_id | legacy_code
-- ------------+-------------
--           1 | x
```

`legacy_code` shows up in `SELECT *`, though on Oracle it would have been
excluded. For `INVISIBLE`'s typical use — hiding a new column from older
code — this is precisely the case the modifier was there to prevent: after
migration, old code doing `SELECT *` unexpectedly receives an extra column.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/invisible_column.py`. It covers `CREATE
TABLE` only; `ALTER TABLE ... MODIFY (col INVISIBLE)` on an existing table
is not tracked yet.
