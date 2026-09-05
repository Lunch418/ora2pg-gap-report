# GAP-093: `RAISERROR` / `THROW` копируются как есть

MSSQL feature: `RAISERROR` и `THROW` — операторы возбуждения ошибки в T-SQL.

## Минимальный пример

```sql
CREATE PROCEDURE dbo.check_amt @amt int AS
BEGIN
    IF @amt < 0
        RAISERROR ('amount must be positive', 16, 1);
END;
```

## Вывод ora2pg (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.check_amt (p_amt integer) AS $body$
BEGIN
BEGIN 
     IF  p_amt < 0
        RAISERROR('amount must be positive', 16, 1);
END;
END;
$body$
```

Оператор скопирован дословно. То же самое происходит с `THROW 50001,
'amount must be positive', 1;`.

## Наблюдаемая проблема

Загрузка проходит чисто — ora2pg выставляет в своём выводе
`check_function_bodies = false`, поэтому тело не разбирается. При
разборе тела на реальном PostgreSQL 16:

```
ERROR:  missing "THEN" at end of SQL expression
LINE 5:         RAISERROR('amount must be positive', 16, 1);
```

(в этом примере первым срабатывает соседний GAP-092 по `IF`; сам
`RAISERROR` не существует в PL/pgSQL независимо от него)

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.**
Переписывается на `RAISE EXCEPTION '<текст>' USING ERRCODE =
'<sqlstate>'`. При переносе стоит помнить о двух вещах: severity в
`RAISERROR` (второй аргумент) соответствует в PostgreSQL не коду
ошибки, а уровню сообщения (`RAISE NOTICE`/`WARNING`/`EXCEPTION`), а
номера ошибок из `THROW` (>= 50000) нужно отобразить на пятизначные
SQLSTATE самостоятельно. Реализовано:
`ora2pg_gap_report/detectors/mssql_raiserror.py`.
