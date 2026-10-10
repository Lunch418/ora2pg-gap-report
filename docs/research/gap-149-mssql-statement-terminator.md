# GAP-149: T-SQL statements without `;` - ora2pg drops what follows

T-SQL feature: `;` is optional. SSMS writes each object as a statement followed by a `GO` line, with no `;`.

## How it was found

Running --migrate --load-check on jOOQ's Sakila (MySQL and SQL Server editions), the Employees database and Microsoft's sample databases (pubs, Northwind), and reading what no known gap explained.

## Minimal example

`tests/fixtures/dialect_corpus_gaps/mssql_source.sql`:

```sql
CREATE TABLE store (
  store_id INT NOT NULL,
  manager_id INT NOT NULL,
  PRIMARY KEY NONCLUSTERED (store_id)
)
GO
 CREATE  INDEX idx_fk_store_id ON store(store_id)
GO

CREATE TABLE staff (
  ...
  PRIMARY KEY NONCLUSTERED (staff_id),
)

CREATE TABLE customer (
  ...
)
GO
```

## ora2pg output (v25.0)

```sql
CREATE TABLE store (
	store_id integer NOT NULL,
	manager_id integer NOT NULL
) ;
ALTER TABLE store ADD PRIMARY KEY (store_id);
```

ora2pg 25.0 (-M) converts the first statement and drops everything after it up to the next `;`: here `staff` and `customer`, with their indexes. Nothing is said, in the output or on the console.

## Observed problem

What is not in the output does not fail to load - it is simply not there:

| Source | Tables in ora2pg's output | After --prepare |
|---|---|---|
| this fixture | 1 of 3 | 3 of 3 |
| jOOQ's Sakila for SQL Server | 1 of 16 | 15 of 16 (one more ended by nothing, before the next CREATE TABLE: now handled too) |
| Microsoft's pubs | 70 statements | 88 statements |

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed, severity high, failure_stage conversion.** `--prepare` ends every statement with `;` before its `GO` (and before a `CREATE TABLE` at the start of a line), and drops the `GO` lines (`prepare_mssql_go_separator`, which did this for routines only, for GAP-126). Reported once per file, with the number of such statements: one cause, one fix.

Implemented: `ora2pg_gap_report/detectors/mssql_statement_terminator.py`.
