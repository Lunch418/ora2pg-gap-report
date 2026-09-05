# GAP-081: `DATE_FORMAT(...)` — silently returns a tuple instead of a string

MySQL/MariaDB feature: `DATE_FORMAT(<date>, <format>)` — formatting a
date into a string with MySQL's specifiers (`%Y`, `%m`, `%d`, `%H`,
`%i`, `%s`).

## Minimal example

```sql
CREATE TABLE t22 (id INT PRIMARY KEY, d DATE);
CREATE PROCEDURE p22()
BEGIN
  SELECT DATE_FORMAT(d, '%Y-%m-%d %H:%i:%s') FROM t22;
END;
```

## ora2pg output (v25.0, `-m -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE p22 () AS $body$
BEGIN
  SELECT (d::varchar::timestamp, 'YYYY-MM-%d HH24:MI:SS') FROM t22;
END;
$body$
LANGUAGE PLPGSQL
;
```

There are two separate problems here. First, the function name `to_char`
is absent from the output entirely — what remains is a bare parenthesis
with two comma-separated expressions, i.e. a row-tuple constructor.
Second, not all specifiers were translated: `%Y`/`%m`/`%H`/`%i`/`%s`
became `YYYY`/`MM`/`HH24`/`MI`/`SS`, while `%d` stayed as it was.

## Observed problem

There is no error at any stage — not at load, not when the body is
parsed, not on the call: a tuple is a perfectly legal expression.
Verified on live data, real PostgreSQL 16:

```
=# INSERT INTO t22 VALUES (1, DATE '2024-03-05');
=# SELECT (d::varchar::timestamp, 'YYYY-MM-%d HH24:MI:SS') FROM t22;
              what_ora2pg_generated
-------------------------------------------------
 ("2024-03-05 00:00:00","YYYY-MM-%d HH24:MI:SS")

=# SELECT to_char(d::timestamp, 'YYYY-MM-DD HH24:MI:SS') FROM t22;
       correct
---------------------
 2024-03-05 00:00:00
```

So instead of a formatted string, the result is a pair of the date itself
and a half-translated format string.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage semantic.** The nastiest
class: the migration "succeeded", the schema-load tests are green, and
reports, exports and API responses silently contain something other than
what was there before. Fixed by rewriting to `to_char(<date>,
'YYYY-MM-DD HH24:MI:SS')`, and every format specifier is worth checking
by hand — as `%d` shows, automatic translation cannot be relied on.
Implemented: `ora2pg_gap_report/detectors/mysql_date_format.py`.
