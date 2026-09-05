# GAP-063: оператор `GOTO`

Oracle feature: безусловный переход на метку `<<label>>` внутри
PL/SQL-блока.

## Минимальный пример

```sql
CREATE OR REPLACE PROCEDURE hop IS
  i NUMBER := 0;
BEGIN
  <<again>>
  i := i + 1;
  IF i < 3 THEN
    GOTO again;
  END IF;
END;
/
```

## Вывод ora2pg (v25.0, `-t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE hop () AS $body$
DECLARE
  i bigint := 0;
BEGIN
  <<again>>
  i := i + 1;
  IF i < 3 THEN
    GOTO again;
  END IF;
END;
$body$
LANGUAGE PLPGSQL
;
```

И метка, и `GOTO` скопированы как есть.

## Наблюдаемая проблема

Загрузка проходит чисто (`check_function_bodies = false`):

```
CREATE PROCEDURE
```

Падение — при первом вызове. Подтверждено на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near "i"
LINE 8:   i := i + 1;
          ^
```

В PL/pgSQL оператора `GOTO` нет вообще. Метка `<<again>>` сама по себе
синтаксически допустима (в PL/pgSQL метками помечают блоки и циклы),
поэтому разбор спотыкается на следующей за ней строке.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/goto_statement.py`. Ручная переработка:
переписать на управляющие конструкции — переход назад на
`LOOP`/`CONTINUE`, переход вперёд через кусок кода на `IF`/`ELSE` или на
выделение этого куска во вложенный блок с `EXIT`.
