# GAP-072: `FULLTEXT KEY`/`FULLTEXT INDEX` inside `CREATE TABLE`

MySQL/MariaDB feature: `FULLTEXT KEY <name> (<columns>)` — a full-text
index declared right in the `CREATE TABLE` column list (alongside
`PRIMARY KEY`/`UNIQUE KEY`).

## Minimal example

```sql
CREATE TABLE articles (
  id INT PRIMARY KEY,
  title VARCHAR(200),
  body TEXT,
  FULLTEXT KEY ft_body (title, body)
);
```

## ora2pg output (v25.0, `-m -t TABLE`)

```sql
CREATE TABLE articles (
	id integer,
	title varchar(200),
	body text,
	fulltext KEY
) ;
ALTER TABLE articles ADD PRIMARY KEY (id);
```

`FULLTEXT KEY ft_body (title, body)` is not recognized as an index at
all: the index name (`ft_body`) and the column list (`title, body`) are
lost entirely, while the words `fulltext KEY` themselves stay in the
output in the position where another column definition was expected — as
if `fulltext` were the name of a new column and `KEY` its type.

## Observed problem

Confirmed on a real PostgreSQL 16:

```
ERROR:  type "key" does not exist
LINE 5:  fulltext KEY
                  ^
```

`CREATE TABLE` fails immediately, at schema load.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high.** PostgreSQL has no direct counterpart
to MySQL `FULLTEXT`, but the equivalent is built with `tsvector`/`GIN`.
The full-text index columns are visible in the source `FULLTEXT KEY
(...)` and are restored by hand: `CREATE INDEX ... USING gin
(to_tsvector('...', title || ' ' || body))` after the `CREATE TABLE`
(with the `fulltext KEY` line removed). Implemented:
`ora2pg_gap_report/detectors/mysql_fulltext_index.py`.
