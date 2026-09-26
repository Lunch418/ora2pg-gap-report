# GAP-111: `CREATE TEMPORARY TABLE` становится постоянной общей таблицей

MySQL/MariaDB feature: временная таблица — видна только создавшему её
сеансу и удаляется, когда сеанс заканчивается.

## Минимальный пример

```sql
CREATE TEMPORARY TABLE `cart_tmp` (
  `session_id` int NOT NULL,
  `item` varchar(50) DEFAULT NULL
) ENGINE=InnoDB;
```

## Вывод ora2pg (v25.0, `-m -t TABLE`)

```sql
\set ON_ERROR_STOP ON
CREATE TABLE cart_tmp (
	session_id integer NOT NULL,
	item varchar(50)
) ;
```

`TEMPORARY` исчез.

## Наблюдаемая проблема

Ничего не падает: таблица загружается — как обычная. Проверено на данных
в PostgreSQL 16: один сеанс вставляет строку, второй её читает:

```
сеанс 1:  INSERT INTO cart_tmp VALUES (1, 'sess-A item');
сеанс 2:  SELECT item FROM cart_tmp;   -- 'sess-A item'
          SELECT relpersistence FROM pg_class WHERE relname = 'cart_tmp';  -- p
```

В MySQL у каждого сеанса была своя копия, исчезавшая вместе с ним. После
миграции все сеансы делят одну постоянную таблицу: строки просачиваются
из сеанса в сеанс и копятся навсегда.

Внутри процедуры, функции или триггера инструкция копируется в тело
PL/pgSQL как есть (проверено), где `CREATE TEMPORARY TABLE` значит то же,
что в MySQL, так что этот случай — не данный gap. С `IF NOT EXISTS` ora2pg
сохраняет `TEMPORARY`, но ломает таблицу иначе (GAP-110).

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16. Исходный
диалект: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage semantic** — ошибки нет
ни на одной стадии, а видимость данных между сеансами меняется.
Исправляется вручную: вернуть `TEMPORARY` в сгенерированный
`CREATE TABLE` или перенести создание в код, который таблицей пользуется.

Реализовано: `ora2pg_gap_report/detectors/mysql_temporary_table.py` —
отмечает `CREATE TEMPORARY TABLE` без `IF NOT EXISTS` на верхнем уровне
скрипта.
