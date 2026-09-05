# GAP-079: `LAST_INSERT_ID()`

MySQL/MariaDB feature: the function returning the `AUTO_INCREMENT` value
produced by the most recent insert on the current connection.

## Minimal example

```sql
CREATE TABLE t26 (id INT PRIMARY KEY AUTO_INCREMENT, v INT);
CREATE PROCEDURE p26()
BEGIN
  INSERT INTO t26 (v) VALUES (1);
  SELECT LAST_INSERT_ID();
END;
```

## ora2pg output (v25.0, `-m -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE p26 () AS $body$
BEGIN
  INSERT INTO t26(v) VALUES (1);
  SELECT LAST_INSERT_ID();
END;
$body$
LANGUAGE PLPGSQL
;
```

The call is copied verbatim.

## Observed problem

The load goes through cleanly: both `CREATE TABLE` and `CREATE
PROCEDURE` run without error. The failure comes on a real call,
confirmed on a live PostgreSQL 16:

```
=# CALL p26();
ERROR:  function last_insert_id() does not exist
LINE 1: SELECT LAST_INSERT_ID()
               ^
HINT:  No function matches the given name and argument types.
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** The best
rewrite is `INSERT ... RETURNING <column> INTO <variable>`: the value
comes straight from the insert that was executed, with no reliance on
session state. `currval()`/`lastval()` work too, but `lastval()` has a
subtlety of its own — it refers to the last sequence used at all, not to
a particular table, so in a procedure that inserts into several tables it
is easy to get the wrong value. Implemented:
`ora2pg_gap_report/detectors/mysql_last_insert_id.py`.
