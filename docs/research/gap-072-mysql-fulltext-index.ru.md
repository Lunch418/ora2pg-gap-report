# GAP-072: `FULLTEXT KEY`/`FULLTEXT INDEX` внутри `CREATE TABLE`

MySQL/MariaDB feature: `FULLTEXT KEY <имя> (<столбцы>)` — полнотекстовый
индекс, объявляемый прямо в списке столбцов `CREATE TABLE` (наравне с
`PRIMARY KEY`/`UNIQUE KEY`).

## Минимальный пример

```sql
CREATE TABLE articles (
  id INT PRIMARY KEY,
  title VARCHAR(200),
  body TEXT,
  FULLTEXT KEY ft_body (title, body)
);
```

## Вывод ora2pg (v25.0, `-m -t TABLE`)

```sql
CREATE TABLE articles (
	id integer,
	title varchar(200),
	body text,
	fulltext KEY
) ;
ALTER TABLE articles ADD PRIMARY KEY (id);
```

`FULLTEXT KEY ft_body (title, body)` не распознаётся как индекс вообще:
имя индекса (`ft_body`) и список столбцов (`title, body`) теряются
целиком, а сами слова `fulltext KEY` остаются в выводе на месте, где
ожидалось очередное определение столбца — как будто `fulltext` это имя
нового столбца, а `KEY` — его тип.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16:

```
ERROR:  type "key" does not exist
LINE 5:  fulltext KEY
                  ^
```

`CREATE TABLE` падает немедленно, при загрузке схемы.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high.** У PostgreSQL нет прямого аналога
MySQL `FULLTEXT`, но эквивалент строится через `tsvector`/`GIN`.
Столбцы полнотекстового индекса видны в исходном `FULLTEXT KEY (...)`
и восстанавливаются вручную: `CREATE INDEX ... USING gin
(to_tsvector('...', title || ' ' || body))` после `CREATE TABLE` (с
удалённой строкой `fulltext KEY`). Реализовано:
`ora2pg_gap_report/detectors/mysql_fulltext_index.py`.
