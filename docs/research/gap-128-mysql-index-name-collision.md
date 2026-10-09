# GAP-128: one index name on several tables - the second CREATE INDEX fails

MySQL/MariaDB feature: index names scoped to their table, so the same name
on several tables is fine - `KEY customer_id (customer_id)` in both
`orders` and `invoices`. mysqldump output has this all the time: MySQL
names an index after its column when none is given.

## How it was found

`--migrate --dialect mysql --load-check docker` on a realistic mysqldump,
once its `KEY` clauses were written as `INDEX` (GAP-073).

## Minimal example

```sql
CREATE TABLE `a` (`id` int NOT NULL, `customer_id` int,
  PRIMARY KEY (`id`), INDEX `customer_id` (`customer_id`)) ENGINE=InnoDB;
CREATE TABLE `b` (`id` int NOT NULL, `customer_id` int,
  PRIMARY KEY (`id`), INDEX `customer_id` (`customer_id`)) ENGINE=InnoDB;
```

## ora2pg output (v25.0, `-m -t TABLE`)

```sql
CREATE INDEX customer_id ON a (customer_id);
CREATE INDEX customer_id ON b (customer_id);
```

## Observed problem

In PostgreSQL an index name belongs to the schema:

```
ERROR:  42P07: relation "customer_id" already exists
```

and table `b` is left without its index.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Mechanical:
`--prepare --dialect mysql` (`prepare_mysql_indexes`) renames every index
whose name is used on more than one table to `<table>_<name>`. An index
name is referenced only by DDL and optimizer hints, which do not carry
over anyway. The same rewrite turns `KEY` into `INDEX` (GAP-073) and names
unnamed indexes `<table>_<column>_idx`, which ora2pg would otherwise drop.
With it the fixture loads with every index in place
(`tests/test_prepare.py`, case g073).

Implemented: `ora2pg_gap_report/detectors/mysql_index_name_collision.py` -
reported at each use after the first table's.
