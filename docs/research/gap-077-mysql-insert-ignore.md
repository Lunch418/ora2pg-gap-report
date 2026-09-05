# GAP-077: `INSERT IGNORE`

MySQL/MariaDB feature: an insert that turns errors into warnings and
silently skips the offending rows.

## Minimal example

```sql
CREATE TABLE uniq1 (id INT PRIMARY KEY, v INT);
CREATE PROCEDURE add_uniq(IN p_id INT)
BEGIN
  INSERT IGNORE INTO uniq1 (id, v) VALUES (p_id, 1);
END;
```

## ora2pg output (v25.0, `-m -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE add_uniq (IN p_id integer) AS $body$
BEGIN
  INSERT IGNORE INTO uniq1(id, v) VALUES (p_id, 1);
END;
$body$
LANGUAGE PLPGSQL
;
```

Copied verbatim.

## Observed problem

The load goes through cleanly (`check_function_bodies = false` in
ora2pg's output). When the body is parsed on a real PostgreSQL 16:

```
ERROR:  "uniq1" is not a known variable
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** The closest
counterpart is `INSERT ... ON CONFLICT DO NOTHING`, but it is narrower in
scope: MySQL's `IGNORE` suppresses not only unique-key conflicts but
other insert errors as well, down to truncating over-long values and
substituting zeros for invalid dates. If the code relied on precisely
that broad behaviour, a literal translation changes its meaning.
Implemented: `ora2pg_gap_report/detectors/mysql_insert_ignore.py`.
