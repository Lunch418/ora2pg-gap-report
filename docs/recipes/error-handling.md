*English | [Русский](error-handling.ru.md)*

# Errors: raising, catching and naming them

Covers: GAP-060 (`pragma_exception_init`), GAP-071 (`mysql_signal`),
GAP-084 (`mysql_declare_handler`), GAP-093 (`mssql_raiserror`), GAP-094
(`mssql_try_catch`).

## The problem

Each source names its errors differently: Oracle by `ORA-nnnnn` numbers,
MySQL by `SQLSTATE` plus handlers, T-SQL by error numbers with
`TRY`/`CATCH`. PostgreSQL uses five-character `SQLSTATE` codes and one
construct, `BEGIN ... EXCEPTION WHEN ... END`. What `ora2pg` does with the
differences:

- `PRAGMA EXCEPTION_INIT(e, -1)` becomes `WHEN SQLSTATE '50001'` whatever
  the number was. PostgreSQL never raises `50001`, so the handler never
  fires and an error Oracle handled now escapes (GAP-060).
- MySQL `SIGNAL`/`RESIGNAL` are copied as they are, and `DECLARE ...
  HANDLER` is dropped: error handling disappears without a trace (GAP-071,
  GAP-084).
- T-SQL `RAISERROR`/`THROW` and `BEGIN TRY`/`BEGIN CATCH` are copied as
  they are (GAP-093, GAP-094).

## Oracle: give each named exception its real SQLSTATE

```plsql
DECLARE
    dup_key EXCEPTION;
    PRAGMA EXCEPTION_INIT(dup_key, -1);
BEGIN
    INSERT INTO uniq_t (id) VALUES (1);
EXCEPTION
    WHEN dup_key THEN
        DBMS_OUTPUT.PUT_LINE('handled duplicate');
END;
```

```sql
CREATE TABLE uniq_t (id integer PRIMARY KEY);
CREATE TABLE handled (what text);
INSERT INTO uniq_t VALUES (1);

DO $$
BEGIN
    INSERT INTO uniq_t (id) VALUES (1);
EXCEPTION
    WHEN unique_violation THEN          -- ORA-00001, SQLSTATE 23505
        INSERT INTO handled VALUES ('duplicate');
END $$;

DO $$
BEGIN
    ASSERT (SELECT what FROM handled) = 'duplicate';
END $$;
```

The Oracle errors that code most often names, and what PostgreSQL raises
for the same failure:

| Oracle | PostgreSQL condition | SQLSTATE |
|---|---|---|
| ORA-00001 unique constraint | `unique_violation` | `23505` |
| ORA-01400 cannot insert NULL | `not_null_violation` | `23502` |
| ORA-02290 check constraint | `check_violation` | `23514` |
| ORA-02291 / ORA-02292 parent/child key | `foreign_key_violation` | `23503` |
| ORA-01403 `NO_DATA_FOUND` | `no_data_found` (only with `SELECT ... INTO STRICT`) | `P0002` |
| ORA-01422 `TOO_MANY_ROWS` | `too_many_rows` (only with `INTO STRICT`) | `P0003` |
| ORA-01476 `ZERO_DIVIDE` | `division_by_zero` | `22012` |
| ORA-01722 `INVALID_NUMBER` | `invalid_text_representation` | `22P02` |
| ORA-06502 `VALUE_ERROR` (too long) | `string_data_right_truncation` | `22001` |
| ORA-06502 `VALUE_ERROR` (out of range) | `numeric_value_out_of_range` | `22003` |
| ORA-00060 deadlock | `deadlock_detected` | `40P01` |
| ORA-00054 resource busy (`NOWAIT`) | `lock_not_available` | `55P03` |
| ORA-08177 can't serialize | `serialization_failure` | `40001` |

`NO_DATA_FOUND` deserves a second look in every routine: a plain
`SELECT ... INTO` in PL/pgSQL does **not** raise when no row is found, it
sets the variable to `NULL`. Only `INTO STRICT` raises. `ora2pg` adds
`STRICT` where it converts `SELECT INTO`; check that it is there wherever
a `WHEN NO_DATA_FOUND` handler expects it.

### RAISE_APPLICATION_ERROR and user-defined exceptions

Oracle's application errors `-20000 .. -20999` need codes of your own. A
`SQLSTATE` is any five letters or digits; pick a class nobody else uses
(here `AP`, for "application") and keep the number:

```sql
CREATE FUNCTION withdraw(p_balance numeric, p_amount numeric)
RETURNS numeric
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_amount > p_balance THEN
        -- RAISE_APPLICATION_ERROR(-20001, 'Insufficient funds');
        RAISE EXCEPTION 'Insufficient funds' USING ERRCODE = 'AP001';
    END IF;
    RETURN p_balance - p_amount;
END;
$$;

DO $$
DECLARE
    v_state text;
    v_message text;
BEGIN
    PERFORM withdraw(10, 20);
    RAISE EXCEPTION 'not reached';
EXCEPTION
    WHEN SQLSTATE 'AP001' THEN     -- WHEN insufficient_funds (EXCEPTION_INIT -20001)
        GET STACKED DIAGNOSTICS v_state = RETURNED_SQLSTATE, v_message = MESSAGE_TEXT;
        ASSERT v_state = 'AP001' AND v_message = 'Insufficient funds';
END $$;
```

| PL/SQL | PL/pgSQL |
|---|---|
| `RAISE_APPLICATION_ERROR(-20001, msg)` | `RAISE EXCEPTION '%', msg USING ERRCODE = 'AP001'` |
| `e EXCEPTION; PRAGMA EXCEPTION_INIT(e, -20001); ... WHEN e` | `WHEN SQLSTATE 'AP001'` |
| `e EXCEPTION; RAISE e;` (no number) | `RAISE EXCEPTION 'e' USING ERRCODE = 'AP...'` |
| `RAISE;` in a handler | `RAISE;` |
| `SQLCODE` | `SQLSTATE` (text, not a number) |
| `SQLERRM` | `SQLERRM` |
| `DBMS_UTILITY.FORMAT_ERROR_BACKTRACE` | `GET STACKED DIAGNOSTICS v = PG_EXCEPTION_CONTEXT` |

Write the codes down in one place (a comment table in the schema, or a
small table of constants): they are now part of the API between the
database and the application, which may test for them.

## MySQL: SIGNAL and handlers

```sql
CREATE FUNCTION check_age(p_age integer)
RETURNS integer
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_age < 0 THEN
        -- SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'age must not be negative';
        RAISE EXCEPTION 'age must not be negative' USING ERRCODE = '45000';
    END IF;
    RETURN p_age;
END;
$$;

DO $$
BEGIN
    PERFORM check_age(-1);
    RAISE EXCEPTION 'not reached';
EXCEPTION
    WHEN SQLSTATE '45000' THEN
        NULL;  -- the same code the MySQL caller tested for
END $$;
```

`DECLARE ... HANDLER` becomes a block, by kind:

| MySQL | PL/pgSQL |
|---|---|
| `DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1` (cursor loop) | `FOR r IN SELECT ... LOOP ... END LOOP` (or `FETCH ...; EXIT WHEN NOT FOUND;`) |
| `DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ... END` | the routine body in `BEGIN ... EXCEPTION WHEN OTHERS THEN ... END` |
| `DECLARE CONTINUE HANDLER FOR SQLEXCEPTION` | only the statement that may fail in its own `BEGIN ... EXCEPTION ... END`, then go on |
| `DECLARE ... HANDLER FOR 1062` (duplicate key) | `WHEN unique_violation` |
| `RESIGNAL` | `RAISE;` |

## T-SQL: RAISERROR, THROW, TRY/CATCH

```sql
CREATE TABLE audit_errors (message text, state text);

CREATE PROCEDURE transfer(p_amount numeric)
LANGUAGE plpgsql
AS $$
BEGIN
    -- BEGIN TRY
    IF p_amount <= 0 THEN
        -- THROW 50001, 'amount must be positive', 1;
        RAISE EXCEPTION 'amount must be positive' USING ERRCODE = 'TS001';
    END IF;
    -- END TRY
EXCEPTION
    -- BEGIN CATCH
    WHEN OTHERS THEN
        INSERT INTO audit_errors VALUES (SQLERRM, SQLSTATE);  -- ERROR_MESSAGE(), ERROR_NUMBER()
    -- END CATCH
END;
$$;

CALL transfer(-5);

DO $$
BEGIN
    ASSERT (SELECT message || '/' || state FROM audit_errors) = 'amount must be positive/TS001';
END $$;
```

| T-SQL | PL/pgSQL |
|---|---|
| `RAISERROR('msg', 16, 1)` (severity 11 and up) | `RAISE EXCEPTION 'msg'` |
| `RAISERROR('msg', 10, 1)` (severity 10 and below) | `RAISE NOTICE 'msg'` |
| `THROW 50001, 'msg', 1` | `RAISE EXCEPTION 'msg' USING ERRCODE = '...'` |
| `THROW;` inside `CATCH` | `RAISE;` |
| `ERROR_MESSAGE()` / `ERROR_NUMBER()` | `SQLERRM` / `SQLSTATE` |
| `ERROR_LINE()`, `ERROR_PROCEDURE()` | `GET STACKED DIAGNOSTICS ... PG_EXCEPTION_CONTEXT` |
| `@@ERROR` after a statement | a `BEGIN ... EXCEPTION` around that statement |

## The difference that changes results

A PostgreSQL `EXCEPTION` block is a savepoint. When an error is caught,
**everything the block did is rolled back** before the handler runs, not
just the failed statement. In T-SQL's `TRY` (without `XACT_ABORT`) and in
MySQL's `CONTINUE` handlers, work done before the error stays. If a
handler relied on earlier statements in the same block having happened,
move those statements out of the block.

```sql
CREATE TABLE steps (n integer);

DO $$
BEGIN
    INSERT INTO steps VALUES (1);           -- outside: survives
    BEGIN
        INSERT INTO steps VALUES (2);       -- inside: undone with the error
        PERFORM 1 / 0;
    EXCEPTION WHEN division_by_zero THEN
        NULL;
    END;
    ASSERT (SELECT array_agg(n) FROM steps) = ARRAY[1];
END $$;
```

Entering a block with an `EXCEPTION` clause costs a savepoint every time.
Inside a loop over many rows, catch outside the loop when you can.
