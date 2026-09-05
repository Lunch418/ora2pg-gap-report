# GAP-006: `table@dblink_name` — прямые ссылки на database link в SQL

Oracle feature: `SELECT ... FROM table@dblink_name` — прямая ссылка на
объект в удалённой базе через `DATABASE LINK` внутри обычного SQL-запроса
(не сам `CREATE DATABASE LINK`, а его использование в запросах).
Распространено в интеграционных/ERP-сценариях — обмен данными между
схемами/базами без промежуточного слоя.

## Минимальный пример

```sql
CREATE OR REPLACE PACKAGE BODY remote_sync_pkg AS
  PROCEDURE pull_remote_orders IS
  BEGIN
    INSERT INTO local_orders (order_id, customer_id, amount)
    SELECT order_id, customer_id, amount
    FROM orders@remote_erp_link
    WHERE created_at > SYSDATE - 1;
    COMMIT;
  END pull_remote_orders;
END remote_sync_pkg;
/
```

## Вывод ora2pg (v25.0, `-t PACKAGE`)

`orders@remote_erp_link` копируется как есть — `@remote_erp_link`
остаётся приклеенным к имени таблицы без каких-либо изменений.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16: `@` — не валидный синтаксис SQL в
PostgreSQL вообще (в имени таблицы недопустим этот символ вне кавычек).
`CREATE PROCEDURE` проходит без ошибки (`check_function_bodies = false` в
выводе ora2pg), падает только при первом реальном вызове:

```
ERROR:  syntax error at or near "@"
LINE 3:     FROM orders@remote_erp_link
```

У PostgreSQL есть архитектурный эквивалент (`postgres_fdw`/`dblink`
расширения + `IMPORT FOREIGN SCHEMA`/foreign tables), но это требует
ручной настройки внешнего сервера и не может быть автоматически
подставлено вместо `@dblink_name` без знания реальных connection-параметров
удалённой базы — потому это гэп, а не что-то, что в принципе можно
конвертировать автоматически.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Отдельно ценно тем, что это распространённый паттерн
в интеграционных Oracle-системах (обмен между схемами/базами), а не
редкая синтаксическая экзотика.

Реализовано: `ora2pg_gap_report/detectors/database_link.py`.
