# GAP-075: `LIMIT <смещение>, <количество>`

MySQL/MariaDB feature: форма постраничной выборки через запятую.

## Минимальный пример

```sql
CREATE TABLE rows2 (id INT PRIMARY KEY, val INT);
CREATE PROCEDURE page_rows()
BEGIN
  SELECT val FROM rows2 ORDER BY id LIMIT 10, 20;
END;
```

## Вывод ora2pg (v25.0, `-m -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE page_rows () AS $body$
BEGIN
  SELECT val FROM rows2 ORDER BY id LIMIT 10, 20;
END;
$body$
LANGUAGE PLPGSQL
;
```

Скопировано дословно.

## Наблюдаемая проблема

`CREATE PROCEDURE` проходит без ошибок — ora2pg выставляет в своём
выводе `check_function_bodies = false`, поэтому тело не разбирается на
загрузке. Ошибка вылезает при разборе тела (проверено принудительным
`check_function_bodies = true` на реальном PostgreSQL 16):

```
ERROR:  LIMIT #,# syntax is not supported
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.**
Переписывается на `LIMIT <количество> OFFSET <смещение>`. Порядок
аргументов в MySQL-форме обратный, поэтому механическая замена запятой
на `OFFSET` без перестановки чисел не падает, а молча выдаёт другую
страницу — это отдельная ловушка при ручной правке. Реализовано:
`ora2pg_gap_report/detectors/mysql_limit_comma.py`.
