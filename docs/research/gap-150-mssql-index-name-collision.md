# GAP-150: one index name on several tables (SQL Server)

T-SQL feature: an index name belongs to its table: `CREATE INDEX idx_fk_store_id ON staff(...)` and `... ON customer(...)`.

## How it was found

Running --migrate --load-check on jOOQ's Sakila (MySQL and SQL Server editions), the Employees database and Microsoft's sample databases (pubs, Northwind), and reading what no known gap explained.

## Minimal example

`tests/fixtures/dialect_corpus_gaps/mssql_source.sql`:

```sql
 CREATE  INDEX idx_fk_store_id ON staff(store_id)
GO
 CREATE  INDEX idx_fk_store_id ON customer(store_id)
GO
```

## ora2pg output (v25.0)

```sql
CREATE INDEX idx_fk_store_id ON staff (store_id);
CREATE INDEX idx_fk_store_id ON customer (store_id);
```

The names are kept. In PostgreSQL an index name belongs to the schema.

## Observed problem

The second one fails, and that table has no index:

```
ERROR:  relation "idx_fk_store_id" already exists
```

Found in jOOQ's Sakila for SQL Server (five names) and Microsoft's pubs (`titleidind`).

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** `--prepare` renames every use after the first table's to `<table>_<name>` (`prepare_mssql_index_names`), as it does for MySQL (GAP-128).

Implemented: `ora2pg_gap_report/detectors/mssql_index_name_collision.py`.
