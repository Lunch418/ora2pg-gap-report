# GAP-082: `FOREIGN KEY` выбрасывается целиком

MySQL/MariaDB feature: внешний ключ, объявляемый в списке столбцов
`CREATE TABLE`.

## Минимальный пример

В том виде, в каком его пишет `mysqldump`:

```sql
CREATE TABLE `customers` (
  `id` int(11) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;
CREATE TABLE `orders2` (
  `id` int(11) NOT NULL,
  `customer_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_orders_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;
```

## Вывод ora2pg (v25.0, `-m -t TABLE`)

```sql
CREATE TABLE orders2 (
	id integer NOT NULL,
	customer_id integer NOT NULL
) ;
ALTER TABLE orders2 ADD PRIMARY KEY (id);
```

Строк `FOREIGN KEY` во всём сгенерированном файле — ноль (проверено
`grep -c`). Ни внутри `CREATE TABLE`, ни отдельным `ALTER TABLE` после
него. То же самое для формы без имени ограничения (`FOREIGN KEY (pid)
REFERENCES parent7 (id)`) — тоже ноль.

## Это не «выгружается отдельным типом экспорта»

Проверено: отдельного типа экспорта под внешние ключи у ora2pg нет.
Полный список поддерживаемых значений `-t` (из сообщения самого
ora2pg 25.0):

```
QUERY, LOAD, SCRIPT, TABLE, VIEW, GRANT, TRIGGER, FUNCTION, PROCEDURE,
PARTITION, DBLINK, SHOW_VERSION, SHOW_REPORT, SHOW_SCHEMA, SHOW_TABLE,
SHOW_COLUMN, SHOW_ENCODING, INSERT, COPY, TEST, TEST_COUNT, TEST_VIEW,
TEST_DATA
```

Ни `FKEY`, ни `CONSTRAINT` в нём нет — попытка `-t FKEY` завершается
`FATAL: Unknown export type`.

## Наблюдаемая проблема

Ошибки не будет ни на загрузке, ни потом: схема поднимется, приложение
заработает, и ссылочная целостность просто перестанет существовать —
вместе с каскадными удалениями, если они были. Заметить это можно
только по последствиям: осиротевшие строки, которые база раньше не
позволяла создать.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage semantic.** По классу
это ровно то, что README называет «архитектурно значимой потерей»:
гарантия, объявленная в определении объекта, исчезает бесследно —
родственно GAP-066 (`WITH READ ONLY`) и GAP-026 (`READ ONLY` на
таблице). Восстанавливается вручную: `ALTER TABLE <таблица> ADD
CONSTRAINT <имя> FOREIGN KEY (<столбцы>) REFERENCES <родитель>
(<столбцы>) ON DELETE ...` после загрузки всех таблиц. Реализовано:
`ora2pg_gap_report/detectors/mysql_foreign_key.py`.
