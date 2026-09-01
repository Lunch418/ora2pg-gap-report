# GAP-084: `DECLARE ... HANDLER` выбрасывается целиком

MySQL/MariaDB feature: обработчик условий в хранимой процедуре —
`DECLARE CONTINUE|EXIT HANDLER FOR SQLEXCEPTION | NOT FOUND |
SQLSTATE '...'`.

## Минимальный пример

```sql
CREATE TABLE h1 (id INT PRIMARY KEY, v INT);
CREATE PROCEDURE safe_insert(IN p_id INT)
BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
    SELECT 'insert failed, ignored';
  INSERT INTO h1 (id, v) VALUES (p_id, 1);
END;
```

## Вывод ora2pg (v25.0, `-m -t PROCEDURE`)

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

На месте обработчика — пустые строки. Ни `EXCEPTION WHEN ...`, ни
какого-либо иного эквивалента в выводе нет (проверено `grep -ci
'handler\|EXCEPTION WHEN'` — ноль совпадений). То же самое для
`DECLARE CONTINUE HANDLER FOR NOT FOUND`.

## Наблюдаемая проблема

Ошибки нет ни на загрузке, ни при вызове: процедура просто теряет всю
обработку ошибок разом. Последствия ровно противоположны исходному
замыслу — то, что MySQL глушил и продолжал выполнение, теперь вылетает
наружу и обрывает транзакцию вызывающего. В примере выше процедура
задумана как «вставить, а при любой ошибке молча выйти»; после
миграции она превращается в «вставить и упасть».

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage semantic.**
Восстанавливается блоком `BEGIN ... EXCEPTION WHEN <условие> THEN ...
END` вокруг нужного участка. Отдельно стоит помнить, что для `NOT
FOUND` прямого соответствия нет: в PL/pgSQL это не условие исключения,
а проверка `FOUND`/`GET DIAGNOSTICS` сразу после запроса, то есть такой
обработчик переписывается не в `EXCEPTION`, а в обычный `IF`.
Реализовано: `ora2pg_gap_report/detectors/mysql_declare_handler.py`.
