# GAP-127: индекс по префиксу столбца ломает файл

Возможность MySQL/MariaDB: индекс по первым N символам столбца - `KEY
idx_note (note(20))`, `UNIQUE KEY uq_code (code(8))`. Для столбцов TEXT и
BLOB MySQL его требует, и mysqldump пишет его как есть.

## Как найден

`--migrate --dialect mysql --load-check docker` на реалистичной выгрузке
mysqldump: с написанием `INDEX` (к которому ведёт GAP-073) сконвертированный
файл не загрузил вообще ничего и ничего об этом не сказал.

## Минимальный пример

`tests/fixtures/mysql_indexes/prefix_index_source.sql`:

```sql
CREATE TABLE `t1` (
  `id` int NOT NULL,
  `note` varchar(200) DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_note` (`note`(20))
) ENGINE=InnoDB;
CREATE TABLE `t2` (`id` int NOT NULL, PRIMARY KEY (`id`)) ENGINE=InnoDB;
```

## Вывод ora2pg (v25.0, `-m -t TABLE`)

```sql
CREATE INDEX idx_note ON t1 (note"(20);
```

для `INDEX`, а для `UNIQUE KEY uq (note(20))`:

```sql
ALTER TABLE t1 ADD UNIQUE ("note(20");
```

Написание `KEY` - это сломанный столбец из GAP-073.

## Наблюдаемая проблема

`"` открывает идентификатор в кавычках, который не закрывается: psql
читает в него весь остаток файла, так что `t2` и всё после индекса не
выполняется. `--load-check` такой файл пропускает и говорит об этом, а не
сообщает, что он загрузился. Вариант UNIQUE падает сам:

```
ERROR:  42703: column "note(20" named in key does not exist
```

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16. Исходный
диалект: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage deployment.** Префиксных
индексов в PostgreSQL нет, единственно верной замены нет, и `--prepare`
такие предложения не трогает. По каждому индексу: индекс по выражению
`left(note, 20)` (что и значил префикс), индекс по всему столбцу (длинные
значения TEXT могут превысить предел строки btree) или без индекса. UNIQUE
по префиксу и UNIQUE по всему столбцу - разные ограничения: первое
отвергает строки, которые второе принимает.

Реализовано: `ora2pg_gap_report/detectors/mysql_index_prefix.py`;
`--load-check` узнаёт форму UNIQUE.
