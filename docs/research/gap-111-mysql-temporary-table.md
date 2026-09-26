# GAP-111: `CREATE TEMPORARY TABLE` becomes a permanent, shared table

MySQL/MariaDB feature: a temporary table — private to the session that
creates it, and dropped when that session ends.

## Minimal example

```sql
CREATE TEMPORARY TABLE `cart_tmp` (
  `session_id` int NOT NULL,
  `item` varchar(50) DEFAULT NULL
) ENGINE=InnoDB;
```

## ora2pg output (v25.0, `-m -t TABLE`)

```sql
\set ON_ERROR_STOP ON
CREATE TABLE cart_tmp (
	session_id integer NOT NULL,
	item varchar(50)
) ;
```

`TEMPORARY` is gone.

## Observed problem

Nothing errors: the table loads, as an ordinary one. Verified on data in
PostgreSQL 16 — one session inserts a row, a second session reads it:

```
session 1:  INSERT INTO cart_tmp VALUES (1, 'sess-A item');
session 2:  SELECT item FROM cart_tmp;   -- 'sess-A item'
            SELECT relpersistence FROM pg_class WHERE relname = 'cart_tmp';  -- p
```

In MySQL each session had its own copy, which disappeared with it. After
the migration every session shares one permanent table: rows leak from
one session into another and pile up forever.

Inside a procedure, function or trigger the statement is copied into the
PL/pgSQL body as written — verified — where `CREATE TEMPORARY TABLE`
means what it did in MySQL, so that case is not this gap. With
`IF NOT EXISTS`, ora2pg keeps `TEMPORARY` and mangles the table instead
(GAP-110).

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage semantic** — no error at
any stage, and data visibility between sessions changes. Fixed by hand:
put `TEMPORARY` back into the generated `CREATE TABLE`, or move the
creation into the code that uses the table.

Implemented: `ora2pg_gap_report/detectors/mysql_temporary_table.py` —
flags a top-level `CREATE TEMPORARY TABLE` without `IF NOT EXISTS`.
