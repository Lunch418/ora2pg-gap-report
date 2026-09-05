# GAP-096: `SCOPE_IDENTITY()` / `@@IDENTITY` копируются как есть

MSSQL feature: `SCOPE_IDENTITY()`, `@@IDENTITY`, `IDENT_CURRENT()` — способы узнать значение, выданное `IDENTITY` при последней вставке.

## Минимальный пример

```sql
CREATE PROCEDURE dbo.add_row AS
BEGIN
    INSERT INTO orders (name) VALUES ('x');
    SELECT SCOPE_IDENTITY();
END;
```

## Вывод ora2pg (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.add_row () AS $body$
DECLARE

;
BEGIN
BEGIN 
     INSERT  INTO orders(name) VALUES ('x');
    SELECT SCOPE_IDENTITY();
END;
END;
$body$
```

Вызов скопирован дословно.

## Наблюдаемая проблема

Ни такой функции, ни такой системной переменной в PostgreSQL нет —
процедура падает при первом же реальном вызове. Загрузка проходит
чисто (`check_function_bodies = false` в выводе ora2pg).

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.**
Переписывается лучше всего на `INSERT ... RETURNING <столбец> INTO
<переменная>`. Учтите, что сам столбец `IDENTITY` при этом тоже теряется
(GAP-090), так что возвращать может быть уже нечего — эти два места
правятся вместе. Реализовано:
`ora2pg_gap_report/detectors/mssql_scope_identity.py`.
