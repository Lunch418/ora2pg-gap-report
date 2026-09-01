# GAP-098: `IIF()` копируется как есть

MSSQL feature: `IIF(<условие>, <если да>, <если нет>)` — тернарный
выбор в T-SQL.

## Минимальный пример

```sql
CREATE PROCEDURE dbo.use_iif AS
BEGIN
    SELECT IIF(amount > 0, 'pos', 'neg'), CHARINDEX('a', nm) FROM orders;
END;
```

## Вывод ora2pg (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.use_iif () AS $body$
DECLARE

;
BEGIN
BEGIN 
     SELECT  IIF(amount > 0, 'pos', 'neg'), position(''a'' in nm) FROM orders;
END;
END;
$body$
```

`IIF` скопирован дословно. Показательно, что соседний `CHARINDEX` в том
же операторе ora2pg перевести пытается (и делает это неверно — см.
GAP-100), то есть `IIF` просто не входит в его таблицу соответствий.

## Наблюдаемая проблема

Функции `IIF` в PostgreSQL нет, и при первом же реальном вызове
процедура падает. Загрузка проходит чисто — ora2pg выставляет в своём
выводе `check_function_bodies = false`.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.**
Переписывается на `CASE WHEN <условие> THEN <если да> ELSE <если нет>
END`. Реализовано: `ora2pg_gap_report/detectors/mssql_iif.py`.
