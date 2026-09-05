# GAP-097: `OUTPUT INSERTED.*` копируется как есть

MSSQL feature: `OUTPUT INSERTED.<столбец>` / `OUTPUT DELETED.<столбец>` — возврат затронутых строк прямо из DML в T-SQL.

## Минимальный пример

```sql
CREATE PROCEDURE dbo.with_output AS
BEGIN
    INSERT INTO orders (nm) OUTPUT INSERTED.id VALUES ('x');
END;
```

## Вывод ora2pg (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.with_output () AS $body$
DECLARE

;
BEGIN
BEGIN 
     INSERT  INTO orders(nm) OUTPUT INSERTED.id VALUES ('x');
END;
END;
$body$
```

Оговорка скопирована дословно.

## Наблюдаемая проблема

В PostgreSQL та же идея пишется как `RETURNING`, слова `OUTPUT` он не
понимает. Загрузка проходит чисто (`check_function_bodies = false` в
выводе ora2pg), падение — при первом вызове.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.**
Переписывается на `RETURNING <столбец>`, но с оглядкой на две вещи:
`RETURNING` не различает `INSERTED` и `DELETED` (для `UPDATE` он
возвращает новые значения — старые придётся брать иначе), и в отличие от
`OUTPUT ... INTO <таблица>` его результат нельзя направить в таблицу
одним оператором. Реализовано:
`ora2pg_gap_report/detectors/mssql_output_clause.py`.
