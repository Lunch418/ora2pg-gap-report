# GAP-074: `SPATIAL KEY`/`SPATIAL INDEX`

MySQL/MariaDB feature: пространственный индекс, объявляемый в списке
столбцов `CREATE TABLE`.

## Минимальный пример

```sql
CREATE TABLE places (
  id INT PRIMARY KEY,
  loc POINT NOT NULL,
  SPATIAL KEY sp_loc (loc)
);
```

## Вывод ora2pg (v25.0, `-m -t TABLE`)

```sql
CREATE TABLE places (
	id integer,
	loc POINT NOT NULL,
	spatial KEY
) ;
ALTER TABLE places ADD PRIMARY KEY (id);
```

Имя индекса (`sp_loc`) и список столбцов (`loc`) потеряны, в выводе
остались только два ключевых слова.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16:

```
ERROR:  type "key" does not exist
LINE 5:  spatial KEY
                 ^
```

`CREATE TABLE` падает немедленно, при загрузке схемы.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high.** Форма поломки совпадает с
GAP-072 (`FULLTEXT KEY`) и GAP-073 (`KEY`), но выделен отдельно
осознанно: и конструкция MySQL другая, и починка другая — не GIN по
`to_tsvector` и не обычный btree, а `CREATE INDEX ... USING gist
(<столбец>)` поверх PostGIS-типа. Отдельно стоит проверить сам тип
столбца: в примере выше `POINT` попал в вывод как есть, и совпадение
имени с типом PostgreSQL `point` не означает совпадения семантики с
пространственными типами MySQL. Реализовано:
`ora2pg_gap_report/detectors/mysql_spatial_index.py`.
