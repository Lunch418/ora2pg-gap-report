# GAP-026: `CREATE TABLE ... READ ONLY` теряет гарантию неизменяемости

Oracle feature: `CREATE TABLE ... READ ONLY` — сервер блокирует любой
`INSERT`/`UPDATE`/`DELETE` в такую таблицу (`ORA-12081`), независимо от
привилегий подключившегося пользователя, включая владельца схемы.

## Минимальный пример

```sql
CREATE TABLE audit_log (
    log_id  NUMBER,
    message VARCHAR2(200)
) READ ONLY;
```

## Вывод ora2pg (v25.0, `-t TABLE`)

```sql
CREATE TABLE audit_log (
	log_id bigint,
	message varchar(200)
) ;
```

Секция `READ ONLY` пропадает без следа.

## Наблюдаемая проблема

Не синтаксическая ошибка — `CREATE TABLE` выполняется без проблем.
Подтверждено на реальном PostgreSQL 16 напрямую:

```sql
INSERT INTO audit_log VALUES (1, 'should have been blocked in Oracle');
-- INSERT 0 1  -- прошло успешно
```

В Oracle этот же `INSERT` гарантированно завершился бы ошибкой
`ORA-12081: update operation not allowed on table`. Потеряна не просто
синтаксическая деталь, а гарантия целостности данных на уровне сервера
— для таблицы-снапшота или исторического архива это может быть
единственной защитой от случайной записи.

У PostgreSQL нет прямого аналога `READ ONLY` для обычной таблицы —
обычно переписывается через `REVOKE INSERT, UPDATE, DELETE` от всех
ролей (включая владельца — в PostgreSQL владелец по умолчанию всё ещё
обходит `REVOKE`, так что нужен более явный механизм) или через
`BEFORE`-триггер, отклоняющий DML явно.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/read_only_table.py`.
