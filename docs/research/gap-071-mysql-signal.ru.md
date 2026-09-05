# GAP-071: `SIGNAL`/`RESIGNAL`

MySQL/MariaDB feature: `SIGNAL`/`RESIGNAL` — операторы возбуждения и
повторного возбуждения условия внутри хранимой процедуры/функции
(аналог `RAISE` в PL/pgSQL).

## Минимальный пример

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

## Вывод ora2pg (v25.0, `-m -t PROCEDURE`)

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

`SIGNAL SQLSTATE '45000' ...` копируется в тело процедуры дословно
(ora2pg попутно теряет ключевое слово `SET` перед `MESSAGE_TEXT`, меняя
его на `:=`, но это ничего не чинит — `SIGNAL` как оператор всё равно
неизвестен PL/pgSQL).

## Наблюдаемая проблема

`CREATE PROCEDURE` проходит без ошибок (`check_function_bodies =
false` в выводе ora2pg). Падение — на первом же реальном вызове,
подтверждено на реальном PostgreSQL 16:

```
=# CALL withdraw(1, 100);
ERROR:  syntax error at or near "SIGNAL"
LINE 1: SIGNAL SQLSTATE '45000' MESSAGE_TEXT := 'insufficient funds'
        ^
QUERY:  SIGNAL SQLSTATE '45000' MESSAGE_TEXT := 'insufficient funds'
CONTEXT:  PL/pgSQL function withdraw(integer,numeric) line 9 at SQL statement
```

Отдельно проверено, что голый `RESIGNAL` (без `SQLSTATE`) в PL/pgSQL
тоже не существует:

```
=# DO $$ BEGIN RESIGNAL; END; $$;
ERROR:  syntax error at or near "RESIGNAL"
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.** Ни
`SIGNAL`, ни `RESIGNAL` в PL/pgSQL не существуют. Переписывается на
`RAISE EXCEPTION ... USING ERRCODE = '<sqlstate>', MESSAGE =
'<текст>'`. Реализовано: `ora2pg_gap_report/detectors/mysql_signal.py`
(детектор ловит оба ключевых слова, `SIGNAL` и `RESIGNAL`).
