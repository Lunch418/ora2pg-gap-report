# GAP-078: `PREPARE <name> FROM <string>`

MySQL/MariaDB feature: preparing dynamic SQL inside a stored procedure
(paired with `EXECUTE` and `DEALLOCATE PREPARE`).

## Minimal example

```sql
CREATE TABLE t25 (id INT PRIMARY KEY);
CREATE PROCEDURE p25()
BEGIN
  SET @s = 'SELECT COUNT(*) FROM t25';
  PREPARE stmt FROM @s;
  EXECUTE stmt;
  DEALLOCATE PREPARE stmt;
END;
```

## ora2pg output (v25.0, `-m -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE p25 () AS $body$
DECLARE
s varchar;

BEGIN
  s := 'SELECT COUNT(*) FROM t25';
  PREPARE stmt FROM s;
  EXECUTE stmt;
  DEALLOCATE PREPARE stmt;
END;
$body$
LANGUAGE PLPGSQL
;
```

ora2pg neatly turned the user variable `@s` into an ordinary PL/pgSQL
variable, but left the `PREPARE ... FROM` statement exactly as it was.

## Observed problem

The load goes through cleanly (`check_function_bodies = false` in
ora2pg's output). When the body is parsed on a real PostgreSQL 16:

```
ERROR:  syntax error at or near "FROM"
```

PostgreSQL does have a `PREPARE` statement, but the syntax differs —
`PREPARE <name> AS <query>` — and the query is given as literal SQL, not
as a string variable.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** The right
rewrite target is not PostgreSQL's `PREPARE` but `EXECUTE <string>`
inside PL/pgSQL: that is the standard way to run SQL assembled in a
variable, parameters are passed via `USING`, and the same mechanism
removes the SQL-injection risk of string concatenation. Implemented:
`ora2pg_gap_report/detectors/mysql_prepare_from.py`.
