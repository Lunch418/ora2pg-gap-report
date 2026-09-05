# GAP-078: `PREPARE <имя> FROM <строка>`

MySQL/MariaDB feature: подготовка динамического SQL в хранимой
процедуре (в связке с `EXECUTE` и `DEALLOCATE PREPARE`).

## Минимальный пример

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

## Вывод ora2pg (v25.0, `-m -t PROCEDURE`)

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

Пользовательскую переменную `@s` ora2pg аккуратно превратил в обычную
переменную PL/pgSQL, а сам оператор `PREPARE ... FROM` оставил как был.

## Наблюдаемая проблема

Загрузка проходит чисто (`check_function_bodies = false` в выводе
ora2pg). При разборе тела на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near "FROM"
```

Оператор `PREPARE` в PostgreSQL есть, но синтаксис другой — `PREPARE
<имя> AS <запрос>`, — и запрос задаётся текстом самого SQL, а не
строковой переменной.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.** Правильная
цель переписывания — не `PREPARE` PostgreSQL, а `EXECUTE <строка>`
внутри PL/pgSQL: это штатный способ выполнить собранный в переменной
SQL, параметры передаются через `USING`, и это же снимает риск
SQL-инъекции при склейке строки. Реализовано:
`ora2pg_gap_report/detectors/mysql_prepare_from.py`.
