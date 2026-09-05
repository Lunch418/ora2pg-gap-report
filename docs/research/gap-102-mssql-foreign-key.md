# GAP-102: `FOREIGN KEY` is dropped entirely (MSSQL)

MSSQL feature: a foreign key declared in the `CREATE TABLE` column list.

## Minimal example

```sql
CREATE TABLE parentx (id int NOT NULL PRIMARY KEY);
CREATE TABLE childx (
    id int NOT NULL PRIMARY KEY,
    pid int NOT NULL,
    CONSTRAINT FK_childx_parentx FOREIGN KEY (pid) REFERENCES parentx (id) ON DELETE CASCADE
);
```

## ora2pg output (v25.0, `-M -t TABLE`)

```sql
CREATE TABLE parentx (
	id integer NOT NULL
) ;
ALTER TABLE parentx ADD PRIMARY KEY (id);


CREATE TABLE childx (
	id integer NOT NULL,
	pid integer NOT NULL
) ;
ALTER TABLE childx ADD PRIMARY KEY (id);
```

There is not a single `FOREIGN KEY` line in the output — neither inside
the `CREATE TABLE` nor as a separate `ALTER TABLE` after it.

## This is not "exported by a separate export type"

ora2pg has no separate export type for foreign keys: the list of
supported `-t` values (`TABLE`, `VIEW`, `GRANT`, `TRIGGER`, `FUNCTION`,
`PROCEDURE`, `PARTITION`, `DBLINK`, `INSERT`, `COPY`, `TEST*`, `SHOW_*`)
contains neither `FKEY` nor `CONSTRAINT`.

## Observed problem

There will be no error at load or afterwards: the schema comes up, the
application runs, and referential integrity simply ceases to exist —
along with the cascading deletes.

ora2pg does exactly the same to foreign keys on the MySQL side
(GAP-082), so this is not a quirk of one dialect.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed, severity high, failure_stage semantic.** Restored by
hand: `ALTER TABLE <table> ADD CONSTRAINT <name> FOREIGN KEY (<columns>)
REFERENCES <parent> (<columns>) ON DELETE ...` after all tables are
loaded. Implemented:
`ora2pg_gap_report/detectors/mssql_foreign_key.py`.
