# GAP-151: `GROUP BY ... WITH ROLLUP` (SQL Server)

T-SQL feature: `GROUP BY a, b WITH ROLLUP` and `WITH CUBE`, the old form of `GROUP BY ROLLUP (a, b)`.

## How it was found

Running --migrate --load-check on jOOQ's Sakila (MySQL and SQL Server editions), the Employees database and Microsoft's sample databases (pubs, Northwind), and reading what no known gap explained.

## Minimal example

`tests/fixtures/dialect_corpus_gaps/mssql_source.sql`:

```sql
CREATE PROCEDURE staff_totals @store INT AS
BEGIN
  SELECT store_id, SUM(amount) AS total FROM staff GROUP BY store_id WITH ROLLUP;
END;
```

## ora2pg output (v25.0)

```sql
   SELECT  store_id, SUM(amount) AS total FROM staff GROUP BY store_id WITH ROLLUP;
```

Copied as it is.

## Observed problem

PostgreSQL knows only `GROUP BY ROLLUP (...)`, and the routine does not load:

```
ERROR:  syntax error at or near "WITH"
```

Found in Microsoft's pubs: three procedures (`group by pub_id with rollup`).

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Mechanical: `--fix` writes `GROUP BY ROLLUP (a, b)` (and `CUBE`), the same grouping (`fix_mssql_with_rollup`).

Implemented: `ora2pg_gap_report/detectors/mssql_with_rollup.py`.
