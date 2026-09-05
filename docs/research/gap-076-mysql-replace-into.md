# GAP-076: `REPLACE INTO`

MySQL/MariaDB feature: insert a row, and if a row with the same unique
key already exists, delete it and insert the new one.

## Minimal example

```sql
CREATE TABLE cache1 (k VARCHAR(50) PRIMARY KEY, v INT);
CREATE PROCEDURE put_cache(IN p_k VARCHAR(50), IN p_v INT)
BEGIN
  REPLACE INTO cache1 (k, v) VALUES (p_k, p_v);
END;
```

## ora2pg output (v25.0, `-m -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE put_cache (IN p_k varchar(50), p_v integer) AS $body$
BEGIN
  REPLACE INTO cache1(k, v) VALUES (p_k, p_v);
END;
$body$
LANGUAGE PLPGSQL
;
```

Copied verbatim, with no conversion whatsoever.

## Observed problem

The load goes through cleanly (`check_function_bodies = false` in
ora2pg's output). When the body is parsed on a real PostgreSQL 16:

```
ERROR:  "cache1" is not a known variable
```

PostgreSQL parses `REPLACE` as the start of a variable assignment rather
than as a statement — it has no `REPLACE INTO` of its own.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** Rewritten to
`INSERT ... ON CONFLICT (<key>) DO UPDATE SET ...`, but the translation
is not literal: `REPLACE` really does delete the old row and insert a new
one, so it fires `ON DELETE` triggers and cascading deletes of child
rows, and columns not listed in the statement get their default values
rather than keeping their previous ones. `ON CONFLICT DO UPDATE` behaves
exactly the opposite way. Implemented:
`ora2pg_gap_report/detectors/mysql_replace_into.py`.
