# GAP-073: `KEY <name> (<columns>)` — a stub instead of an index

MySQL/MariaDB feature: `KEY <name> (<columns>)` — an ordinary
(non-unique) index declared right in the `CREATE TABLE` column list.
This is the spelling `mysqldump` emits by default for every secondary
index, so the construct appears in essentially every real-world dump.

## Minimal example

Taken exactly as `mysqldump` writes it — with backquotes and table
options:

```sql
CREATE TABLE `orders` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `customer_id` int(11) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_customer` (`customer_id`),
  KEY `idx_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## ora2pg output (v25.0, `-m -t TABLE`)

```sql
CREATE TABLE orders (
	id serial,
	customer_id integer NOT NULL,
	created_at timestamp without time zone,
	key IDX_CUSTOMER
) ;
ALTER TABLE orders ADD PRIMARY KEY (id);
```

Two losses at once here. The first index became the stub `key
IDX_CUSTOMER` in the position where another column definition was
expected. The second (`idx_created`) vanished from the output without a
trace.

## Observed problem

Confirmed on a real PostgreSQL 16:

```
ERROR:  type "idx_customer" does not exist
LINE 5:  key IDX_CUSTOMER
             ^
```

PostgreSQL reads `key` as the name of a new column and the index name as
that column's type. `CREATE TABLE` fails immediately, at schema load.

## What does work

Checked separately, and this matters for detector precision — it is not
any index that breaks, but specifically the `KEY` spelling:

```sql
INDEX idx_email (email)      -- the same MySQL construct, a different synonym
```

```sql
CREATE INDEX idx_email ON k3 (email);   -- ported correctly
```

```sql
UNIQUE KEY uq_email (email)
```

```sql
ALTER TABLE k2 ADD UNIQUE (email);      -- ported (the constraint name is lost)
```

The unnamed form `KEY (a)` does not break the load, but disappears from
the output entirely and silently.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high.** This is the widest-reaching gap of the
MySQL batch: `mysqldump` writes `KEY`, not `INDEX`, so essentially every
real schema is affected. Fixed by rewriting to `CREATE INDEX <name> ON
<table> (<columns>)` after the `CREATE TABLE`. Implemented:
`ora2pg_gap_report/detectors/mysql_key_index.py` — the detector
deliberately does not flag `PRIMARY KEY`, `UNIQUE KEY`, `FOREIGN KEY`,
`FULLTEXT KEY` (GAP-072) or `SPATIAL KEY` (GAP-074).
