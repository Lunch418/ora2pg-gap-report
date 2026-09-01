# GAP-068: `ENUM(...)` — ссылка на несуществующий тип

Первый gap из партии MySQL/MariaDB-исследования: ora2pg поддерживает
MySQL как источник напрямую, через `-m`/`--mysql`, и работает файлово
(`-i <file>`, без живого подключения к MySQL) точно так же, как
Oracle-режим (`-t <TYPE> -i <file>`).

MySQL/MariaDB feature: `ENUM(...)` — перечислимый тип, объявляемый
прямо в определении столбца.

## Минимальный пример

```sql
CREATE TABLE orders (
  id INT PRIMARY KEY AUTO_INCREMENT,
  status ENUM('new','paid','shipped','cancelled') NOT NULL DEFAULT 'new'
);
```

## Вывод ora2pg (v25.0, `-m -t TABLE`)

```sql
CREATE TABLE orders (
	id serial,
	status ORDERS_STATUS_T NOT NULL DEFAULT 'new'
) ;
ALTER TABLE orders ADD PRIMARY KEY (id);
```

ora2pg синтезирует под ENUM именованный PostgreSQL-тип
`orders_status_t` и подставляет это имя в определение столбца — сам
подход правильный (PostgreSQL действительно поддерживает `CREATE TYPE
... AS ENUM (...)`), но оператор `CREATE TYPE orders_status_t AS ENUM
('new','paid','shipped','cancelled');`, которым этот тип должен быть
объявлен, в вывод не попадает вообще. В исходном коде `lib/Ora2Pg.pm`
есть плейсхолдер `#ORA2PGENUM#`, который должен заменяться на
сгенерированный `CREATE TYPE` — здесь замена не происходит.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16:

```
ERROR:  type "orders_status_t" does not exist
LINE 3:  status ORDERS_STATUS_T NOT NULL DEFAULT 'new'
                ^
```

`CREATE TABLE` падает немедленно, при загрузке схемы — до какого-либо
`INSERT`/вызова процедуры.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high.** Значения перечисления при этом
нигде не теряются — они видны прямо в исходном `ENUM(...)`, — так что
исправление механическое: вставить недостающий `CREATE TYPE
<таблица>_<столбец>_t AS ENUM (...)` перед `CREATE TABLE` для каждого
ENUM-столбца. Severity здесь high, а не medium (как у похожего по духу
`sdo_geometry`/GAP-067), потому что там отображение типа выбрано верно
и не хватает одной универсальной строки `CREATE EXTENSION postgis`,
одинаковой для любой таблицы; здесь же для каждого ENUM-столбца нужен
свой собственный `CREATE TYPE` со своим набором значений — не одна
универсальная строка, а по одной вставке на каждый столбец. Реализовано:
`ora2pg_gap_report/detectors/mysql_enum_type.py`.
