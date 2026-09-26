# GAP-110: `CREATE TABLE IF NOT EXISTS` becomes a table called `if`

MySQL/MariaDB feature: `CREATE TABLE IF NOT EXISTS`, common in
hand-maintained schema scripts and in exports from tools other than
mysqldump.

## Minimal example

```sql
CREATE TABLE IF NOT EXISTS `customers` (
  `id` int NOT NULL,
  `name` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;
```

## ora2pg output (v25.0, `-m -t TABLE`)

```sql
\set ON_ERROR_STOP ON
CREATE TABLE if (
	not EXISTS NOT NULL DEFAULT NULL,
  
) ENGINE=InnoDB
) ;
ALTER TABLE if ADD PRIMARY KEY (id);
```

The table parser takes the word after `TABLE` as the table's name: the
table is called `if`, its real name and its columns are gone.

## Observed problem

```
ERROR:  syntax error at or near "not"
```

at load time, and `\set ON_ERROR_STOP ON` stops the load of the whole
schema there. A/B: the same table without `IF NOT EXISTS` converts and
loads.

`CREATE TEMPORARY TABLE IF NOT EXISTS` comes out as `CREATE TEMPORARY
TABLE if (…)`, the same way. Inside a procedure, function or trigger the
statement is copied into the PL/pgSQL body as written — verified — and
PostgreSQL accepts `IF NOT EXISTS` there, so that case is not this gap.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Fixed before
converting by dropping `IF NOT EXISTS` — the converted schema is loaded
into an empty database anyway.

Implemented:
`ora2pg_gap_report/detectors/mysql_create_table_if_not_exists.py` —
flags a top-level `CREATE [TEMPORARY] TABLE IF NOT EXISTS`, not one
inside a routine body. The Oracle 23ai counterpart is GAP-112.
