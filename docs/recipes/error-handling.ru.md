*[English](error-handling.md) | Русский*

# Ошибки: как бросать, ловить и называть

Покрывает: GAP-060 (`pragma_exception_init`), GAP-071 (`mysql_signal`),
GAP-084 (`mysql_declare_handler`), GAP-093 (`mssql_raiserror`), GAP-094
(`mssql_try_catch`).

## Проблема

Каждый источник называет ошибки по-своему: Oracle номерами `ORA-nnnnn`,
MySQL кодом `SQLSTATE` и обработчиками, T-SQL номерами ошибок и
`TRY`/`CATCH`. PostgreSQL использует пятисимвольные коды `SQLSTATE` и одну
конструкцию, `BEGIN ... EXCEPTION WHEN ... END`. Что `ora2pg` делает с
этими различиями:

- `PRAGMA EXCEPTION_INIT(e, -1)` превращается в `WHEN SQLSTATE '50001'`,
  каким бы ни был номер. PostgreSQL никогда не выдаёт `50001`, поэтому
  обработчик не срабатывает, и ошибка, которую Oracle обрабатывал, теперь
  уходит наружу (GAP-060).
- `SIGNAL`/`RESIGNAL` из MySQL копируются как есть, а `DECLARE ... HANDLER`
  выбрасывается: обработка ошибок исчезает без следа (GAP-071, GAP-084).
- `RAISERROR`/`THROW` и `BEGIN TRY`/`BEGIN CATCH` из T-SQL копируются как
  есть (GAP-093, GAP-094).

## Oracle: дайте каждому именованному исключению его настоящий SQLSTATE

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

Ошибки Oracle, которые код называет чаще всего, и что PostgreSQL выдаёт на
тот же сбой:

| Oracle | Условие PostgreSQL | SQLSTATE |
|---|---|---|
| ORA-00001 уникальное ограничение | `unique_violation` | `23505` |
| ORA-01400 нельзя вставить NULL | `not_null_violation` | `23502` |
| ORA-02290 ограничение CHECK | `check_violation` | `23514` |
| ORA-02291 / ORA-02292 родительский/дочерний ключ | `foreign_key_violation` | `23503` |
| ORA-01403 `NO_DATA_FOUND` | `no_data_found` (только с `SELECT ... INTO STRICT`) | `P0002` |
| ORA-01422 `TOO_MANY_ROWS` | `too_many_rows` (только с `INTO STRICT`) | `P0003` |
| ORA-01476 `ZERO_DIVIDE` | `division_by_zero` | `22012` |
| ORA-01722 `INVALID_NUMBER` | `invalid_text_representation` | `22P02` |
| ORA-06502 `VALUE_ERROR` (слишком длинно) | `string_data_right_truncation` | `22001` |
| ORA-06502 `VALUE_ERROR` (вне диапазона) | `numeric_value_out_of_range` | `22003` |
| ORA-00060 взаимоблокировка | `deadlock_detected` | `40P01` |
| ORA-00054 ресурс занят (`NOWAIT`) | `lock_not_available` | `55P03` |
| ORA-08177 нельзя сериализовать | `serialization_failure` | `40001` |

`NO_DATA_FOUND` стоит перепроверить в каждой подпрограмме: обычный
`SELECT ... INTO` в PL/pgSQL **не** выдаёт ошибку, если строка не найдена,
а записывает в переменную `NULL`. Ошибку выдаёт только `INTO STRICT`.
`ora2pg` добавляет `STRICT`, когда конвертирует `SELECT INTO`; проверьте,
что он стоит везде, где обработчик `WHEN NO_DATA_FOUND` на это
рассчитывает.

### RAISE_APPLICATION_ERROR и свои исключения

Прикладным ошибкам Oracle `-20000 .. -20999` нужны свои коды. `SQLSTATE` -
это любые пять букв или цифр; возьмите класс, которым больше никто не
пользуется (здесь `AP`, "application"), и сохраните номер:

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
| `e EXCEPTION; RAISE e;` (без номера) | `RAISE EXCEPTION 'e' USING ERRCODE = 'AP...'` |
| `RAISE;` в обработчике | `RAISE;` |
| `SQLCODE` | `SQLSTATE` (текст, а не число) |
| `SQLERRM` | `SQLERRM` |
| `DBMS_UTILITY.FORMAT_ERROR_BACKTRACE` | `GET STACKED DIAGNOSTICS v = PG_EXCEPTION_CONTEXT` |

Запишите коды в одном месте (таблица в комментарии к схеме или маленькая
таблица констант): теперь они часть интерфейса между базой и приложением,
которое может их проверять.

## MySQL: SIGNAL и обработчики

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
        NULL;  -- тот же код, который проверял вызывающий код в MySQL
END $$;
```

`DECLARE ... HANDLER` становится блоком, в зависимости от вида:

| MySQL | PL/pgSQL |
|---|---|
| `DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1` (цикл по курсору) | `FOR r IN SELECT ... LOOP ... END LOOP` (или `FETCH ...; EXIT WHEN NOT FOUND;`) |
| `DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ... END` | тело подпрограммы в `BEGIN ... EXCEPTION WHEN OTHERS THEN ... END` |
| `DECLARE CONTINUE HANDLER FOR SQLEXCEPTION` | только команда, которая может упасть, в своём `BEGIN ... EXCEPTION ... END`, дальше работа продолжается |
| `DECLARE ... HANDLER FOR 1062` (повтор ключа) | `WHEN unique_violation` |
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
| `RAISERROR('msg', 16, 1)` (уровень 11 и выше) | `RAISE EXCEPTION 'msg'` |
| `RAISERROR('msg', 10, 1)` (уровень 10 и ниже) | `RAISE NOTICE 'msg'` |
| `THROW 50001, 'msg', 1` | `RAISE EXCEPTION 'msg' USING ERRCODE = '...'` |
| `THROW;` внутри `CATCH` | `RAISE;` |
| `ERROR_MESSAGE()` / `ERROR_NUMBER()` | `SQLERRM` / `SQLSTATE` |
| `ERROR_LINE()`, `ERROR_PROCEDURE()` | `GET STACKED DIAGNOSTICS ... PG_EXCEPTION_CONTEXT` |
| `@@ERROR` после команды | `BEGIN ... EXCEPTION` вокруг этой команды |

## Разница, которая меняет результат

Блок `EXCEPTION` в PostgreSQL - это точка сохранения. Когда ошибка
поймана, **всё, что сделал блок, откатывается** до запуска обработчика, а
не только упавшая команда. В `TRY` из T-SQL (без `XACT_ABORT`) и в
обработчиках `CONTINUE` из MySQL работа, сделанная до ошибки, остаётся. Если
обработчик рассчитывал, что предыдущие команды того же блока выполнились,
вынесите эти команды из блока.

```sql
CREATE TABLE steps (n integer);

DO $$
BEGIN
    INSERT INTO steps VALUES (1);           -- снаружи: остаётся
    BEGIN
        INSERT INTO steps VALUES (2);       -- внутри: откатывается вместе с ошибкой
        PERFORM 1 / 0;
    EXCEPTION WHEN division_by_zero THEN
        NULL;
    END;
    ASSERT (SELECT array_agg(n) FROM steps) = ARRAY[1];
END $$;
```

Каждый вход в блок с `EXCEPTION` стоит точки сохранения. Внутри цикла по
множеству строк по возможности ловите ошибку снаружи цикла.
