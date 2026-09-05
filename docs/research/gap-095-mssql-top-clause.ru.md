# GAP-095: `SELECT TOP n` копируется как есть

MSSQL feature: `SELECT TOP <n>` — ограничение числа строк в T-SQL.

## Минимальный пример

```sql
CREATE PROCEDURE dbo.topn @n int AS
BEGIN
    SELECT TOP 10 id FROM orders;
END;
```

## Вывод ora2pg (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.topn (p_n integer) AS $body$
BEGIN
BEGIN 
     SELECT  TOP 10 id FROM orders;
END;
END;
$body$
```

Скопировано дословно.

## Наблюдаемая проблема

Загрузка проходит чисто — ora2pg выставляет в своём выводе
`check_function_bodies = false`, поэтому тело не разбирается. При
разборе тела на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near "10"
LINE 4:      SELECT  TOP 10 id FROM orders;
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.**
Переписывается на `LIMIT <n>` в конце запроса. Отдельно стоит проверить
`TOP` без `ORDER BY`: в T-SQL так пишут часто, и при переносе на `LIMIT`
порядок строк остаётся столь же неопределённым — если на него
полагались, нужен явный `ORDER BY`. Форма `TOP (<n>) PERCENT` прямого
аналога не имеет вовсе. Реализовано:
`ora2pg_gap_report/detectors/mssql_top_clause.py`.
