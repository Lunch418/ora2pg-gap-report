# GAP-075: `LIMIT <offset>, <count>`

MySQL/MariaDB feature: the comma form of paginated selection.

## Minimal example

```sql
CREATE TABLE rows2 (id INT PRIMARY KEY, val INT);
CREATE PROCEDURE page_rows()
BEGIN
  SELECT val FROM rows2 ORDER BY id LIMIT 10, 20;
END;
```

## ora2pg output (v25.0, `-m -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE page_rows () AS $body$
BEGIN
  SELECT val FROM rows2 ORDER BY id LIMIT 10, 20;
END;
$body$
LANGUAGE PLPGSQL
;
```

Copied verbatim.

## Observed problem

`CREATE PROCEDURE` succeeds without error — ora2pg sets
`check_function_bodies = false` in its own output, so the body is not
parsed at load time. The error surfaces when the body is parsed
(verified by forcing `check_function_bodies = true` on a real PostgreSQL
16):

```
ERROR:  LIMIT #,# syntax is not supported
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** Rewritten to
`LIMIT <count> OFFSET <offset>`. The argument order in the MySQL form is
reversed, so mechanically replacing the comma with `OFFSET` without
swapping the numbers does not fail — it silently returns a different
page, which is a trap of its own during manual editing. Implemented:
`ora2pg_gap_report/detectors/mysql_limit_comma.py`.
