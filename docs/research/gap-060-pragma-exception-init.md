# GAP-060: `PRAGMA EXCEPTION_INIT` — обработчик становится мёртвым кодом

Oracle feature: привязка объявленного исключения к номеру ошибки Oracle,
чтобы ловить её по имени в `WHEN`.

## Минимальный пример

```sql
CREATE OR REPLACE PROCEDURE ins_one IS
  dup_key EXCEPTION;
  PRAGMA EXCEPTION_INIT(dup_key, -1);
BEGIN
  INSERT INTO uniq_t (id) VALUES (1);
EXCEPTION
  WHEN dup_key THEN
    DBMS_OUTPUT.PUT_LINE('handled duplicate');
END;
/
```

ORA-00001 — нарушение уникальности. В Oracle процедура печатает
`handled duplicate`.

## Вывод ora2pg (v25.0, `-t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE ins_one () AS $body$
BEGIN
  INSERT INTO uniq_t(id) VALUES (1);
EXCEPTION
  WHEN SQLSTATE '50001' THEN
    RAISE NOTICE 'handled duplicate';
END;
$body$
LANGUAGE PLPGSQL
;
```

Сам `PRAGMA` выброшен, обработчик переписан на `WHEN SQLSTATE '50001'`.

## Наблюдаемая проблема

`'50001'` — константа, не зависящая от номера ORA. Проверено на двух
разных: `-1` (ORA-00001, уникальность) и `-60` (ORA-00060,
взаимоблокировка) — в обоих случаях в выводе `SQLSTATE '50001'`.

Процедура создаётся без единой ошибки:

```
CREATE PROCEDURE
```

Дальше — реальный вызов против реального ограничения уникальности.
Подтверждено на PostgreSQL 16:

```
ERROR:  duplicate key value violates unique constraint "uniq_t_pkey"
DETAIL:  Key (id)=(1) already exists.
CONTEXT:  SQL statement "INSERT INTO uniq_t(id) VALUES (1)"
PL/pgSQL function ins_one() line 3 at SQL statement
```

Обработчик не сработал. Настоящий код PostgreSQL для этой ошибки —
`23505`, что проверено тут же:

```
NOTICE:  unique_violation SQLSTATE = 23505
```

PostgreSQL никогда не возбуждает `50001`, поэтому обработчик становится
мёртвым кодом, а обработанная в Oracle ошибка после миграции молча
вылетает наружу и роняет вызывающий код.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/pragma_exception_init.py`. Ручная
переработка: сопоставить каждый номер ORA с настоящим кодом PostgreSQL и
заменить `'50001'` на него — или на именованное условие вроде
`unique_violation` / `deadlock_detected`, что читается лучше.
