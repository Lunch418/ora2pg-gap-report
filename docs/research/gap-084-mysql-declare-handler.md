# GAP-084: `DECLARE ... HANDLER` is dropped entirely

MySQL/MariaDB feature: a condition handler in a stored procedure —
`DECLARE CONTINUE|EXIT HANDLER FOR SQLEXCEPTION | NOT FOUND |
SQLSTATE '...'`.

## Minimal example

```sql
CREATE TABLE h1 (id INT PRIMARY KEY, v INT);
CREATE PROCEDURE safe_insert(IN p_id INT)
BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
    SELECT 'insert failed, ignored';
  INSERT INTO h1 (id, v) VALUES (p_id, 1);
END;
```

## ora2pg output (v25.0, `-m -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE safe_insert (IN p_id integer) AS $body$
DECLARE


BEGIN
  
  INSERT INTO h1(id, v) VALUES (p_id, 1);
END;
$body$
LANGUAGE PLPGSQL
;
```

Where the handler was, there are blank lines. Neither `EXCEPTION WHEN
...` nor any other equivalent appears in the output (verified with `grep
-ci 'handler\|EXCEPTION WHEN'` — zero matches). Same for `DECLARE
CONTINUE HANDLER FOR NOT FOUND`.

## Observed problem

No error at load or on call: the procedure simply loses all its error
handling at once. The consequences are the exact opposite of the original
intent — what MySQL swallowed while continuing execution now escapes and
aborts the caller's transaction. In the example above the procedure is
meant to "insert, and on any error exit silently"; after migration it
becomes "insert and fail".

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage semantic.** Restored with
a `BEGIN ... EXCEPTION WHEN <condition> THEN ... END` block around the
relevant section. Worth remembering separately that `NOT FOUND` has no
direct counterpart: in PL/pgSQL it is not an exception condition but a
`FOUND`/`GET DIAGNOSTICS` check right after the query, so such a handler
is rewritten into an ordinary `IF`, not into `EXCEPTION`. Implemented:
`ora2pg_gap_report/detectors/mysql_declare_handler.py`.
