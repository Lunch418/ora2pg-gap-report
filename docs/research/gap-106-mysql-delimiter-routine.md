# GAP-106: a routine written under `DELIMITER` does not load

MySQL/MariaDB feature: the `DELIMITER` client directive. A procedure or
function body contains `;`, so the `mysql` client needs another
statement delimiter to send the whole routine as one statement.
`mysqldump` writes every routine this way (`DELIMITER ;;` … `END ;;` …
`DELIMITER ;`), and so does practically every hand-written MySQL script.

## Minimal example

```sql
DELIMITER //
CREATE FUNCTION add_one(p INT) RETURNS int DETERMINISTIC
BEGIN
  RETURN p + 1;
END //
DELIMITER ;
```

## ora2pg output (v25.0, `-m -t FUNCTION`)

```sql
\set ON_ERROR_STOP ON
CREATE OR REPLACE FUNCTION add_one (p integer) RETURNS integer AS $body$
BEGIN
  RETURN p + 1;
END //
DELIMITER ;
$body$
LANGUAGE PLPGSQL
 IMMUTABLE;
```

ora2pg ends a routine's body at an Oracle-style `END <name>;` and does not
know the `DELIMITER` directive: the closing `//` and the `DELIMITER ;` line
end up inside `$body$`. In a `mysqldump` file everything up to the next
routine goes in as well — the `/*!50003 SET sql_mode = ... */` lines
mysqldump writes around every routine.

## Observed problem

The generated `CREATE` fails at load time:

```
ERROR:  syntax error at or near "//"
```

and the output's own `\set ON_ERROR_STOP ON` stops the load of the whole
file there. The same failure for every delimiter tried, for procedures
(`-t PROCEDURE`) and functions (`-t FUNCTION`) alike:

| Delimiter | Error at load |
|---|---|
| `;;` | `syntax error at or near "DELIMITER"` |
| `//` | `syntax error at or near "//"` |
| `$$` | `unterminated dollar-quoted string` |
| `\|` | `syntax error at or near "\|"` |
| `$` | `syntax error at or near "$"` |

A/B: the same function ended with a plain `;` and no `DELIMITER` loads,
and `SELECT add_one(41)` returns 42.

On a real `mysqldump --routines` of sakila taken from MySQL 8.0.46 (its six
routines plus one test procedure), `-t FUNCTION` generated all seven, and
loading the file into PostgreSQL 16 created none of them.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Fixed before
converting: remove the `DELIMITER` directives and end each routine with a
plain `;` — ora2pg reads the file itself, not through the `mysql` client,
so it has no use for them.

Implemented: `ora2pg_gap_report/detectors/mysql_delimiter_routine.py` —
flags each `CREATE PROCEDURE`/`FUNCTION` that stands where a delimiter
other than `;` is in force. A routine inside an executable comment
(`/*!50003 ... */`) is not flagged here: ora2pg drops those entirely,
which is GAP-109.
