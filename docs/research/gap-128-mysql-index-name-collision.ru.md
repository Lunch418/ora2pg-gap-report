# GAP-128: одно имя индекса на нескольких таблицах - второй CREATE INDEX падает

Возможность MySQL/MariaDB: имя индекса принадлежит его таблице, поэтому
одно и то же имя на нескольких таблицах допустимо - `KEY customer_id
(customer_id)` и в `orders`, и в `invoices`. В выгрузках mysqldump это
сплошь и рядом: без явного имени MySQL называет индекс по столбцу.

## Как найден

`--migrate --dialect mysql --load-check docker` на реалистичной выгрузке
mysqldump после того, как её `KEY` были записаны как `INDEX` (GAP-073).

## Минимальный пример

```sql
CREATE TABLE `a` (`id` int NOT NULL, `customer_id` int,
  PRIMARY KEY (`id`), INDEX `customer_id` (`customer_id`)) ENGINE=InnoDB;
CREATE TABLE `b` (`id` int NOT NULL, `customer_id` int,
  PRIMARY KEY (`id`), INDEX `customer_id` (`customer_id`)) ENGINE=InnoDB;
```

## Вывод ora2pg (v25.0, `-m -t TABLE`)

```sql
CREATE INDEX customer_id ON a (customer_id);
CREATE INDEX customer_id ON b (customer_id);
```

## Наблюдаемая проблема

В PostgreSQL имя индекса принадлежит схеме:

```
ERROR:  42P07: relation "customer_id" already exists
```

и таблица `b` остаётся без индекса.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16. Исходный
диалект: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage deployment.** Механически:
`--prepare --dialect mysql` (`prepare_mysql_indexes`) переименовывает
каждый индекс, чьё имя встречается больше чем на одной таблице, в
`<таблица>_<имя>`. На имя индекса ссылаются только DDL и подсказки
оптимизатору, которые и так не переносятся. Та же перезапись превращает
`KEY` в `INDEX` (GAP-073) и даёт безымянным индексам имя
`<таблица>_<столбец>_idx`, иначе ora2pg их выбрасывает. С ней фикстура
загружается со всеми индексами (`tests/test_prepare.py`, случай g073).

Реализовано: `ora2pg_gap_report/detectors/mysql_index_name_collision.py` -
сообщается на каждом использовании после первой таблицы.
