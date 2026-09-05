# GAP-100: `CHARINDEX()` переводится в `position()` с удвоенными кавычками

MSSQL feature: `CHARINDEX(<что искать>, <где искать>)` — поиск
подстроки.

## Минимальный пример

```sql
CREATE PROCEDURE dbo.ci @nm varchar(50) AS
BEGIN
    SELECT CHARINDEX('abc', @nm);
END;
```

## Вывод ora2pg (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.ci (p_nm varchar(50)) AS $body$
BEGIN
BEGIN 
     SELECT  position(''abc'' in p_nm);
END;
END;
$body$
```

В отличие от прочих встроенных функций этой партии, `CHARINDEX` ora2pg
переводить пытается — и цель выбирает верную, `position(... in ...)`, —
но удваивает кавычки вокруг искомой строки.

## Наблюдаемая проблема

`position(''abc'' in p_nm)` — это уже не валидный SQL. Подтверждено на
реальном PostgreSQL 16:

```
ERROR:  syntax error at or near "abc"
LINE 4:      SELECT  position(''abc'' in p_nm);
```

Загрузка проходит чисто (`check_function_bodies = false` в выводе
ora2pg), ошибка вылезает при первом вызове.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.** Это не
«конструкции нет в PostgreSQL», а именно ошибка перевода: цель верная,
испорчено экранирование. Чинится снятием лишних кавычек —
`position('abc' in p_nm)`. Имейте в виду, что у `CHARINDEX` есть третий
аргумент (позиция начала поиска), которому у `position()` прямого
соответствия нет и который переносится через `substring()`.
Реализовано: `ora2pg_gap_report/detectors/mssql_charindex.py`.
