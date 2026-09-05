# GAP-064: `<курсор>%ROWTYPE`

Oracle feature: объявление переменной по структуре курсора.

## Минимальный пример

```sql
CREATE OR REPLACE PROCEDURE walk IS
  CURSOR c IS SELECT emp_id, name FROM employees;
  r c%ROWTYPE;
BEGIN
  OPEN c; FETCH c INTO r; CLOSE c;
END;
/
```

## Вывод ora2pg (v25.0, `-t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE walk () AS $body$
DECLARE
  c CURSOR FOR SELECT emp_id, name FROM employees;
  r c%ROWTYPE;
BEGIN
  OPEN c;FETCH c INTO r;CLOSE c;
END;
$body$
LANGUAGE PLPGSQL
;
```

Объявление самого курсора переписано верно (`CURSOR c IS` → `c CURSOR
FOR`), а `c%ROWTYPE` оставлено как есть.

## Наблюдаемая проблема

Загрузка проходит чисто (`check_function_bodies = false`):

```
CREATE PROCEDURE
```

Падение — при первом вызове. Подтверждено на реальном PostgreSQL 16:

```
ERROR:  relation "c" does not exist
CONTEXT:  compilation of PL/pgSQL function "walk" near line 5
```

PL/pgSQL понимает `%ROWTYPE` только от таблицы или представления, но не
от курсора, поэтому имя курсора трактуется как имя отношения.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/cursor_rowtype.py`. Детектор помечает
`%ROWTYPE` только от имени, объявленного как `CURSOR` в том же файле:
обычное `<таблица>%ROWTYPE` ora2pg переносит корректно, и помечать его
было бы ложным срабатыванием.

Ручная переработка: объявить переменную как `RECORD` — в PL/pgSQL
переменная этого типа принимает строку любого курсора, и `FETCH` в неё
работает без изменений.
