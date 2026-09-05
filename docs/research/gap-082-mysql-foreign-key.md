# GAP-082: `FOREIGN KEY` is dropped entirely

MySQL/MariaDB feature: a foreign key declared in the `CREATE TABLE`
column list.

## Minimal example

As `mysqldump` writes it:

```sql
CREATE TABLE `customers` (
  `id` int(11) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;
CREATE TABLE `orders2` (
  `id` int(11) NOT NULL,
  `customer_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_orders_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;
```

## ora2pg output (v25.0, `-m -t TABLE`)

```sql
CREATE TABLE orders2 (
	id integer NOT NULL,
	customer_id integer NOT NULL
) ;
ALTER TABLE orders2 ADD PRIMARY KEY (id);
```

`FOREIGN KEY` lines in the whole generated file: zero (verified with
`grep -c`). Neither inside the `CREATE TABLE` nor as a separate `ALTER
TABLE` after it. Same for the form without a constraint name (`FOREIGN
KEY (pid) REFERENCES parent7 (id)`) — also zero.

## This is not "exported by a separate export type"

Verified: ora2pg has no separate export type for foreign keys. The full
list of supported `-t` values (from ora2pg 25.0's own message):

```
QUERY, LOAD, SCRIPT, TABLE, VIEW, GRANT, TRIGGER, FUNCTION, PROCEDURE,
PARTITION, DBLINK, SHOW_VERSION, SHOW_REPORT, SHOW_SCHEMA, SHOW_TABLE,
SHOW_COLUMN, SHOW_ENCODING, INSERT, COPY, TEST, TEST_COUNT, TEST_VIEW,
TEST_DATA
```

Neither `FKEY` nor `CONSTRAINT` is in it — trying `-t FKEY` ends with
`FATAL: Unknown export type`.

## Observed problem

There will be no error at load or afterwards: the schema comes up, the
application runs, and referential integrity simply ceases to exist —
along with the cascading deletes, if there were any. The only way to
notice is by the consequences: orphaned rows the database used to
prevent.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage semantic.** By class this
is exactly what the README calls an "architecturally significant loss": a
guarantee declared in the object definition disappears without a trace —
akin to GAP-066 (`WITH READ ONLY`) and GAP-026 (`READ ONLY` on a table).
Restored by hand: `ALTER TABLE <table> ADD CONSTRAINT <name> FOREIGN KEY
(<columns>) REFERENCES <parent> (<columns>) ON DELETE ...` after all
tables are loaded. Implemented:
`ora2pg_gap_report/detectors/mysql_foreign_key.py`.
