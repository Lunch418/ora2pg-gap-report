# GAP-071: `SIGNAL`/`RESIGNAL`

MySQL/MariaDB feature: `SIGNAL`/`RESIGNAL` — the statements that raise
and re-raise a condition inside a stored procedure/function (the
counterpart of `RAISE` in PL/pgSQL).

## Minimal example

```sql
CREATE TABLE accounts (
  id INT PRIMARY KEY,
  balance DECIMAL(12,2) NOT NULL
);

CREATE PROCEDURE withdraw(IN p_id INT, IN p_amount DECIMAL(12,2))
BEGIN
  DECLARE cur_balance DECIMAL(12,2);
  SELECT balance INTO cur_balance FROM accounts WHERE id = p_id;
  IF cur_balance < p_amount THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'insufficient funds';
  END IF;
  UPDATE accounts SET balance = balance - p_amount WHERE id = p_id;
END;
```

## ora2pg output (v25.0, `-m -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE withdraw (IN p_id integer, p_amount decimal(12,2)) AS $body$
DECLARE

cur_balance decimal(12,2);
BEGIN
  
  SELECT balance INTO cur_balance FROM accounts WHERE id = p_id;
  IF cur_balance < p_amount THEN
    SIGNAL SQLSTATE '45000' MESSAGE_TEXT := 'insufficient funds';
  END IF;
  UPDATE accounts SET balance = balance - p_amount WHERE id = p_id;
END;
$body$
LANGUAGE PLPGSQL
;
```

`SIGNAL SQLSTATE '45000' ...` is copied into the procedure body verbatim
(along the way ora2pg loses the `SET` keyword before `MESSAGE_TEXT`,
turning it into `:=`, but that fixes nothing — `SIGNAL` as a statement is
unknown to PL/pgSQL either way).

## Observed problem

`CREATE PROCEDURE` succeeds without error (`check_function_bodies =
false` in ora2pg's output). The failure comes on the very first real
call, confirmed on a real PostgreSQL 16:

```
=# CALL withdraw(1, 100);
ERROR:  syntax error at or near "SIGNAL"
LINE 1: SIGNAL SQLSTATE '45000' MESSAGE_TEXT := 'insufficient funds'
        ^
QUERY:  SIGNAL SQLSTATE '45000' MESSAGE_TEXT := 'insufficient funds'
CONTEXT:  PL/pgSQL function withdraw(integer,numeric) line 9 at SQL statement
```

Checked separately that bare `RESIGNAL` (without `SQLSTATE`) does not
exist in PL/pgSQL either:

```
=# DO $$ BEGIN RESIGNAL; END; $$;
ERROR:  syntax error at or near "RESIGNAL"
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high, failure_stage runtime.** Neither
`SIGNAL` nor `RESIGNAL` exists in PL/pgSQL. It is rewritten to `RAISE
EXCEPTION ... USING ERRCODE = '<sqlstate>', MESSAGE = '<text>'`.
Implemented: `ora2pg_gap_report/detectors/mysql_signal.py` (the detector
catches both keywords, `SIGNAL` and `RESIGNAL`).
