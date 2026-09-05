# GAP-073: `KEY <имя> (<столбцы>)` — обрубок вместо индекса

MySQL/MariaDB feature: `KEY <имя> (<столбцы>)` — обычный (не уникальный)
индекс, объявляемый прямо в списке столбцов `CREATE TABLE`. Это
написание по умолчанию выдаёт `mysqldump` для каждого вторичного
индекса, поэтому конструкция встречается практически в любом реальном
дампе.

## Минимальный пример

Взят в том виде, в каком его пишет `mysqldump` — с обратными кавычками
и опциями таблицы:

```sql
CREATE TABLE `orders` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `customer_id` int(11) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_customer` (`customer_id`),
  KEY `idx_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## Вывод ora2pg (v25.0, `-m -t TABLE`)

```sql
CREATE TABLE orders (
	id serial,
	customer_id integer NOT NULL,
	created_at timestamp without time zone,
	key IDX_CUSTOMER
) ;
ALTER TABLE orders ADD PRIMARY KEY (id);
```

Здесь две потери сразу. Первый индекс превратился в обрубок `key
IDX_CUSTOMER` на месте, где ожидалось очередное определение столбца.
Второй (`idx_created`) исчез из вывода бесследно.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16:

```
ERROR:  type "idx_customer" does not exist
LINE 5:  key IDX_CUSTOMER
             ^
```

PostgreSQL читает `key` как имя нового столбца, а имя индекса — как имя
типа для него. `CREATE TABLE` падает немедленно, при загрузке схемы.

## Что при этом работает

Проверено отдельно, и это важно для точности детектора — ломается не
любой индекс, а именно написание `KEY`:

```sql
INDEX idx_email (email)      -- та же конструкция MySQL, другой синоним
```

```sql
CREATE INDEX idx_email ON k3 (email);   -- переносится корректно
```

```sql
UNIQUE KEY uq_email (email)
```

```sql
ALTER TABLE k2 ADD UNIQUE (email);      -- переносится (теряется имя ограничения)
```

Безымянная форма `KEY (a)` загрузку не ломает, но пропадает из вывода
целиком и молча.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high.** Это самый заметный по охвату gap
MySQL-партии: `mysqldump` пишет `KEY`, а не `INDEX`, поэтому под него
попадает практически любая реальная схема. Чинится переписыванием в
`CREATE INDEX <имя> ON <таблица> (<столбцы>)` после `CREATE TABLE`.
Реализовано: `ora2pg_gap_report/detectors/mysql_key_index.py` — детектор
намеренно не помечает `PRIMARY KEY`, `UNIQUE KEY`, `FOREIGN KEY`,
`FULLTEXT KEY` (GAP-072) и `SPATIAL KEY` (GAP-074).
