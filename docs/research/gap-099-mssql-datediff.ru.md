# GAP-099: `DATEDIFF()` копируется как есть

MSSQL feature: `DATEDIFF(<единица>, <начало>, <конец>)` — разница дат.

## Минимальный пример

```sql
CREATE PROCEDURE dbo.datefns AS
BEGIN
    SELECT DATEADD(day, 7, created), DATEDIFF(day, created, GETDATE()), DATEPART(year, created) FROM orders;
END;
```

## Вывод ora2pg (v25.0, `-M -t PROCEDURE`)

```sql
     SELECT  created + INTERVAL '7 day', DATEDIFF(day, created, date_trunc('millisecond', CURRENT_TIMESTAMP::timestamp)), date_part('year', created) FROM orders;
```

Соседние функции переведены правильно: `DATEADD` стал арифметикой с
`INTERVAL`, `DATEPART` — `date_part()`, `GETDATE()` — выражением с
`CURRENT_TIMESTAMP`. А `DATEDIFF` остался как был.

## Наблюдаемая проблема

Функции `DATEDIFF` в PostgreSQL нет. Загрузка проходит чисто
(`check_function_bodies = false` в выводе ora2pg), падение — при первом
реальном вызове.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.**
Переписывается через вычитание: разница в днях — `(<конец>::date -
<начало>::date)`, в остальных единицах — через `EXTRACT(EPOCH FROM
(<конец> - <начало>))` с делением. Обратите внимание на семантику:
T-SQL `DATEDIFF` считает пересечённые границы единиц, а не полные
интервалы, поэтому `DATEDIFF(year, ...)` между 31 декабря и 1 января
даёт 1, а прямое вычитание даст 0. Реализовано:
`ora2pg_gap_report/detectors/mssql_datediff.py`.
