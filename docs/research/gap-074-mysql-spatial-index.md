# GAP-074: `SPATIAL KEY`/`SPATIAL INDEX`

MySQL/MariaDB feature: a spatial index declared in the `CREATE TABLE`
column list.

## Minimal example

```sql
CREATE TABLE places (
  id INT PRIMARY KEY,
  loc POINT NOT NULL,
  SPATIAL KEY sp_loc (loc)
);
```

## ora2pg output (v25.0, `-m -t TABLE`)

```sql
CREATE TABLE places (
	id integer,
	loc POINT NOT NULL,
	spatial KEY
) ;
ALTER TABLE places ADD PRIMARY KEY (id);
```

The index name (`sp_loc`) and the column list (`loc`) are lost; only the
two keywords remain in the output.

## Observed problem

Confirmed on a real PostgreSQL 16:

```
ERROR:  type "key" does not exist
LINE 5:  spatial KEY
                 ^
```

`CREATE TABLE` fails immediately, at schema load.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Verdict

**Gap confirmed, severity high.** The shape of the breakage matches
GAP-072 (`FULLTEXT KEY`) and GAP-073 (`KEY`), but it is kept separate
deliberately: the MySQL construct is different and so is the fix — not a
GIN index over `to_tsvector` and not a plain btree, but `CREATE INDEX
... USING gist (<column>)` on top of a PostGIS type. The column type
itself is worth checking separately: in the example above `POINT` made it
into the output as-is, and a name matching PostgreSQL's `point` type does
not mean the semantics match MySQL's spatial types. Implemented:
`ora2pg_gap_report/detectors/mysql_spatial_index.py`.
