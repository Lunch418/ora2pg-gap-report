# GAP-091: процедура без параметров получает пустой `DECLARE`

MSSQL feature: хранимая процедура без параметров — как правило, все
служебные и отчётные.

## Минимальный пример

```sql
CREATE PROCEDURE dbo.noparams AS
BEGIN
    UPDATE t SET a = 1;
END;
```

## Вывод ora2pg (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.noparams () AS $body$
DECLARE

;
BEGIN
...
```

Блок объявлений пустой: `DECLARE`, пустая строка и одинокая точка с
запятой.

## Изоляция

Проверено прямым сравнением с точно такой же процедурой, у которой есть
параметр:

```sql
CREATE PROCEDURE dbo.withparams @x int AS
BEGIN
    UPDATE t SET a = @x;
END;
```

```sql
CREATE OR REPLACE PROCEDURE dbo.withparams (p_x integer) AS $body$
BEGIN
...
```

Блока `DECLARE` нет вовсе, тело начинается сразу с `BEGIN`. То есть
сломанный `DECLARE` появляется ровно тогда, когда параметров нет.

## Наблюдаемая проблема

Загрузка проходит чисто (`check_function_bodies = false` в выводе
ora2pg). При разборе тела на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near ";"
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.** Чинится
удалением пустого `DECLARE` из готового кода (или добавлением в него
реальных переменных, если они нужны). Реализовано:
`ora2pg_gap_report/detectors/mssql_parameterless_procedure.py` —
детектор помечает процедуру, у которой между именем и `AS` нет ни
одного `@`-параметра.
