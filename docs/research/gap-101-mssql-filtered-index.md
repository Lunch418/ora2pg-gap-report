# GAP-101: a filtered index is dropped entirely

MSSQL feature: a filtered index — `CREATE INDEX ... WHERE <condition>`,
an index over part of a table's rows.

## Minimal example

```sql
CREATE TABLE soft_del (
    id int NOT NULL PRIMARY KEY,
    deleted bit NOT NULL
);
CREATE NONCLUSTERED INDEX IX_alive ON soft_del (id) WHERE deleted = 0;
```

## ora2pg output (v25.0, `-M -t TABLE`)

```sql
CREATE TABLE soft_del (
	id integer NOT NULL,
	deleted boolean NOT NULL
) ;
ALTER TABLE soft_del ADD PRIMARY KEY (id);
```

The index is absent from the output entirely.

## This is not a general problem with indexes

Verified separately: an ordinary index with `INCLUDE` is ported correctly
by the same ora2pg in the same run.

```sql
CREATE NONCLUSTERED INDEX IX_lookup_a ON lookup1 (a) INCLUDE (b, c);
```

```sql
CREATE INDEX ix_lookup_a ON lookup1 (a) INCLUDE (b, c);
```

It loads without error (PostgreSQL has supported `INCLUDE` since 11). So
it is the filtered form specifically that is lost.

## Observed problem

There will be no error at load or afterwards: the schema comes up without
the index. The difference shows up as plan degradation on large tables
and, if the index was `UNIQUE`, as a vanished uniqueness constraint as
well.

The most galling part is that there is almost nothing to port here:
PostgreSQL has exactly the same partial indexes with exactly the same
syntax.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed, severity high, failure_stage semantic.** Restored by
carrying the statement over verbatim after the schema is loaded.
Implemented: `ora2pg_gap_report/detectors/mssql_filtered_index.py`.
