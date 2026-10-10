# GAP-152: `GROUP BY ... WITH ROLLUP` (MySQL)

MySQL feature: `GROUP BY a, b WITH ROLLUP`, its form of `GROUP BY ROLLUP (a, b)`.

## How it was found

Running --migrate --load-check on jOOQ's Sakila (MySQL and SQL Server editions), the Employees database and Microsoft's sample databases (pubs, Northwind), and reading what no known gap explained.

## Minimal example

`tests/fixtures/dialect_corpus_gaps/mysql_source.sql`:

```sql
CREATE TABLE payment (store_id INT NOT NULL, amount INT NOT NULL);
CREATE VIEW payment_totals AS SELECT store_id, SUM(amount) AS total FROM payment GROUP BY store_id WITH ROLLUP;
```

## ora2pg output (v25.0)

```sql
CREATE OR REPLACE VIEW payment_totals AS SELECT store_id, SUM(amount) AS total FROM payment GROUP BY store_id WITH ROLLUP;
```

Copied as it is, in views and routines alike.

## Observed problem

The view does not load:

```
ERROR:  syntax error at or near "WITH"
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Mechanical: `--fix` writes `GROUP BY ROLLUP (store_id)` (`fix_mysql_with_rollup`), checked: with rows (1, 10), (1, 5), (2, 7) the view returns 15, 7 and the total 22, as MySQL's WITH ROLLUP does.

Implemented: `ora2pg_gap_report/detectors/mysql_with_rollup.py`.
