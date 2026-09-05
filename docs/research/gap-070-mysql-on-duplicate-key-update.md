# GAP-070: `INSERT ... ON DUPLICATE KEY UPDATE`

MySQL/MariaDB feature: `ON DUPLICATE KEY UPDATE` — an upsert construct:
if the insert conflicts with a unique key/`PRIMARY KEY`, update the
existing row instead of raising an error.

## Minimal example

```sql
CREATE TABLE counters (
  id INT PRIMARY KEY,
  hits INT NOT NULL DEFAULT 0
);

CREATE PROCEDURE bump(IN p_id INT)
BEGIN
  INSERT INTO counters (id, hits) VALUES (p_id, 1)
    ON DUPLICATE KEY UPDATE hits = hits + 1;
END;
```

## ora2pg output (v25.0, `-m -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE bump (IN p_id integer) AS $body$
BEGIN
  INSERT INTO counters(id, hits) VALUES (p_id, 1)
    ON DUPLICATE KEY UPDATE hits = hits + 1;
END;
$body$
LANGUAGE PLPGSQL
;
```

The whole `ON DUPLICATE KEY UPDATE` statement is copied into the
procedure body verbatim, with no conversion to `ON CONFLICT` whatsoever.

## Observed problem

`CREATE PROCEDURE` succeeds without error — ora2pg sets
`check_function_bodies = false` in its own output, so the body is not
parsed at load time. The failure happens on the very first real call,
confirmed on a real PostgreSQL 16:

```
=# CALL bump(1);
ERROR:  syntax error at or near "DUPLICATE"
LINE 2:     ON DUPLICATE KEY UPDATE hits = hits + 1
               ^
QUERY:  INSERT INTO counters(id, hits) VALUES (p_id, 1)
    ON DUPLICATE KEY UPDATE hits = hits + 1
CONTEXT:  PL/pgSQL function bump(integer) line 3 at SQL statement
```

Loading the schema itself (`CREATE TABLE`, `CREATE PROCEDURE`) goes
through cleanly — at that stage the error cannot be noticed at all, only
on a real call.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** PostgreSQL's
`INSERT` has no such syntax at all — it is rewritten to `INSERT ... ON
CONFLICT (<unique_key>) DO UPDATE SET ...`. Implemented:
`ora2pg_gap_report/detectors/mysql_on_duplicate_key_update.py`.
