# GAP-110: `CREATE TABLE IF NOT EXISTS` превращается в таблицу `if`

MySQL/MariaDB feature: `CREATE TABLE IF NOT EXISTS`, частый в рукописных
скриптах схемы и в выгрузках других инструментов, кроме mysqldump.

## Минимальный пример

```sql
CREATE TABLE IF NOT EXISTS `customers` (
  `id` int NOT NULL,
  `name` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;
```

## Вывод ora2pg (v25.0, `-m -t TABLE`)

```sql
\set ON_ERROR_STOP ON
CREATE TABLE if (
	not EXISTS NOT NULL DEFAULT NULL,
  
) ENGINE=InnoDB
) ;
ALTER TABLE if ADD PRIMARY KEY (id);
```

Разбор таблиц берёт слово после `TABLE` за имя таблицы: таблица
называется `if`, её настоящее имя и столбцы потеряны.

## Наблюдаемая проблема

```
ERROR:  syntax error at or near "not"
```

при загрузке, и `\set ON_ERROR_STOP ON` останавливает загрузку всей
схемы. A/B: та же таблица без `IF NOT EXISTS` конвертируется и
загружается.

`CREATE TEMPORARY TABLE IF NOT EXISTS` выходит как
`CREATE TEMPORARY TABLE if (…)` — так же. Внутри процедуры, функции или
триггера инструкция копируется в тело PL/pgSQL как есть (проверено), а
PostgreSQL там `IF NOT EXISTS` принимает, так что этот случай — не данный
gap.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16. Исходный
диалект: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage deployment.** Исправляется
до конвертации удалением `IF NOT EXISTS` — сконвертированная схема всё
равно загружается в пустую базу.

Реализовано:
`ora2pg_gap_report/detectors/mysql_create_table_if_not_exists.py` —
отмечает `CREATE [TEMPORARY] TABLE IF NOT EXISTS` на верхнем уровне
скрипта, но не внутри тела подпрограммы. Аналог для Oracle 23ai — GAP-112.
