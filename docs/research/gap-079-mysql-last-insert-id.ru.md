# GAP-079: `LAST_INSERT_ID()`

MySQL/MariaDB feature: функция, возвращающая значение `AUTO_INCREMENT`,
выданное последней вставкой в текущем соединении.

## Минимальный пример

```sql
CREATE TABLE t26 (id INT PRIMARY KEY AUTO_INCREMENT, v INT);
CREATE PROCEDURE p26()
BEGIN
  INSERT INTO t26 (v) VALUES (1);
  SELECT LAST_INSERT_ID();
END;
```

## Вывод ora2pg (v25.0, `-m -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE p26 () AS $body$
BEGIN
  INSERT INTO t26(v) VALUES (1);
  SELECT LAST_INSERT_ID();
END;
$body$
LANGUAGE PLPGSQL
;
```

Вызов скопирован дословно.

## Наблюдаемая проблема

Загрузка проходит чисто: и `CREATE TABLE`, и `CREATE PROCEDURE`
выполняются без ошибок. Падение — на реальном вызове, подтверждено на
живом PostgreSQL 16:

```
=# CALL p26();
ERROR:  function last_insert_id() does not exist
LINE 1: SELECT LAST_INSERT_ID()
               ^
HINT:  No function matches the given name and argument types.
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.** Лучший
вариант переписывания — `INSERT ... RETURNING <столбец> INTO
<переменная>`: значение берётся прямо из выполненной вставки, без
обращения к состоянию сессии. `currval()`/`lastval()` тоже работают, но
у `lastval()` своя тонкость — он относится к последней использованной
последовательности вообще, а не к конкретной таблице, поэтому в
процедуре, вставляющей в несколько таблиц, легко получить чужое
значение. Реализовано:
`ora2pg_gap_report/detectors/mysql_last_insert_id.py`.
