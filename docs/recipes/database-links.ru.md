*[English](database-links.md) | Русский*

# Database link -> postgres_fdw

Покрывает: GAP-006 (`database_link`).

## Проблема

`SELECT ... FROM employees@hr_link` читает таблицу в другой базе через
database link. `ora2pg` копирует ссылку как есть, а синтаксиса `@` в
PostgreSQL нет, и команда падает. В PostgreSQL до другой базы добираются
через обёртку сторонних данных: `postgres_fdw` для другой базы PostgreSQL
(входит в поставку PostgreSQL) и `oracle_fdw`, если другая сторона остаётся
на Oracle.

## Приём: одна схема на link

Назовите локальную схему так же, как link, и импортируйте в неё удалённые
таблицы. Тогда `employees@hr_link` становится `hr_link.employees` -
механическая замена каждой ссылки, без других изменений в запросе.

```sql
CREATE EXTENSION IF NOT EXISTS postgres_fdw;

-- CREATE DATABASE LINK hr_link CONNECT TO hr IDENTIFIED BY ... USING 'hrdb';
CREATE SERVER hr_link
    FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host 'localhost', dbname 'postgres');

-- Учётные данные хранятся в сопоставлении пользователя, а не в коде.
CREATE USER MAPPING FOR CURRENT_USER
    SERVER hr_link
    OPTIONS (user 'postgres');

CREATE SCHEMA hr_link;
```

Подключите удалённые таблицы, все или по списку:

```pgsql
IMPORT FOREIGN SCHEMA public LIMIT TO (employees, departments)
    FROM SERVER hr_link INTO hr_link;
```

или объявите одну вручную, если нужны не все столбцы или другое имя.
Проверка ниже объявляет внешнюю таблицу над системным представлением,
которое есть в любой базе, и читает его через link:

```sql
CREATE FOREIGN TABLE hr_link.remote_schemas (nspname name)
    SERVER hr_link
    OPTIONS (schema_name 'pg_catalog', table_name 'pg_namespace');

DO $$
BEGIN
    -- SELECT count(*) FROM pg_namespace@hr_link
    ASSERT (SELECT count(*) FROM hr_link.remote_schemas WHERE nspname = 'pg_catalog') = 1;
END $$;
```

Сами ссылки можно заменить одним регулярным выражением по
сгенерированному коду (`(\w+)@(\w+)` -> `\2.\1`) и потом просмотреть: это
тот же запрос, только теперь он читает `hr_link.employees`.

## Что не переносится

- **Удалённые вызовы процедур.** `hr_pkg.raise_salary@hr_link(...)` через
  внешнюю таблицу не сделать. Используйте расширение `dblink`:
  `SELECT dblink_exec('hr_link', 'CALL hr_pkg_raise_salary(...)')`, где
  `hr_link` может быть тем же сторонним сервером (`dblink` принимает имя
  сервера).
- **Распределённые транзакции.** Oracle коммитит обе стороны link
  двухфазным коммитом. `postgres_fdw` коммитит удалённую сторону вместе с
  локальной транзакцией, но не атомарно с ней: сбой между ними может
  оставить закоммиченной только одну сторону. Код, который пишет в обе базы
  и рассчитывает на "всё или ничего", нужно спроектировать иначе (одна
  база или таблица исходящих сообщений, которую обрабатывают потом).
- **Синонимы поверх link.** `CREATE SYNONYM emp FOR employees@hr_link` в
  PostgreSQL - представление:
  `CREATE VIEW emp AS SELECT * FROM hr_link.employees`.

## На что обратить внимание

- **Производительность.** `postgres_fdw` передаёт на удалённую сторону
  `WHERE`, соединения таблиц одного сервера, сортировки и агрегаты, но не
  всё. Посмотрите план каждого запроса, который ходил через link
  (`EXPLAIN VERBOSE` показывает удалённый SQL), и добавьте в параметры
  сервера `use_remote_estimate 'true'`, если порядок соединений
  получается неудачным.
- **Кто может подключаться.** Пользователю без прав суперпользователя
  нужен пароль в сопоставлении. Создайте сопоставление на каждую роль,
  которая пользуется link, или одно `FOR PUBLIC` для общей технической
  учётной записи.
- **Изолированная сеть.** Link, который в Oracle пересекал границу
  безопасности, пересекает её и в PostgreSQL. Обёртка не меняет того, кому
  с кем можно общаться; уточните у того, кто отвечает за эту границу.
