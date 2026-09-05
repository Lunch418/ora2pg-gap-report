# GAP-094: `BEGIN TRY` / `BEGIN CATCH` копируются как есть

MSSQL feature: `BEGIN TRY ... END TRY BEGIN CATCH ... END CATCH` — обработка ошибок в T-SQL.

## Минимальный пример

```sql
CREATE PROCEDURE dbo.safe_op AS
BEGIN
    BEGIN TRY
        INSERT INTO t1 (id) VALUES (1);
    END TRY
    BEGIN CATCH
        SELECT ERROR_MESSAGE();
    END CATCH
END;
```

## Вывод ora2pg (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.safe_op () AS $body$
DECLARE

;
BEGIN
BEGIN 
     BEGIN  TRY
        INSERT INTO t1(id) VALUES (1);
    END TRY
    BEGIN CATCH
        SELECT ERROR_MESSAGE();
    END CATCH
END;
END;
$body$
```

Вся конструкция скопирована дословно, включая `END TRY` и `END CATCH`.

## Наблюдаемая проблема

Загрузка проходит чисто — ora2pg выставляет в своём выводе
`check_function_bodies = false`, поэтому тело не разбирается. При
разборе тела на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near ";"
```

(в этом примере первым срабатывает GAP-091 — процедура без параметров;
сам `BEGIN TRY` в PL/pgSQL не существует независимо от него)

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.**
Переписывается на блок `BEGIN ... EXCEPTION WHEN OTHERS THEN ... END`,
причём вызовы внутри `CATCH` тоже меняются: `ERROR_MESSAGE()` — это
`SQLERRM`, `ERROR_NUMBER()` — `SQLSTATE`. Реализовано:
`ora2pg_gap_report/detectors/mssql_try_catch.py`.
