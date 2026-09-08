# GAP-102: `FOREIGN KEY` is dropped when `PG_VERSION` is left at its default (MSSQL)

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

## ora2pg output with an unconfigured `PG_VERSION` (v25.0, `-M -i schema.sql -t TABLE`)

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

There is not a single `FOREIGN KEY` line in the output.

```sh
ora2pg -c myconf.conf -M -i schema.sql -t TABLE -o out.sql -b out   # myconf.conf has PG_VERSION 16
```

```sql
ALTER TABLE childx ADD CONSTRAINT fk_childx_parentx FOREIGN KEY (pid) REFERENCES parentx(id) ON DELETE NO ACTION INITIALLY IMMEDIATE;
```

Same schema, same `-M -i -t TABLE`, the only difference is `PG_VERSION`
in the config.

## Same root cause as GAP-082, not the file-based path

Two earlier versions of this document each gave a different wrong
mechanism: first that `-t` has no export type for foreign keys, then
that file-based input has no live catalog to consult so the
dialect-specific `_foreign_key()` (a live-query-only function) can never
return anything. Both read like reasonable explanations of the observed
zero-FK output; neither is what actually causes it.

The real mechanism lives in dialect-agnostic code shared by every
source engine, `_create_unique_keys()` and `_create_foreign_keys()` in
`lib/Ora2Pg.pm`, and GAP-082 traces it in full with `perl -d`-style
instrumentation: an `exists $self->{partitions_list}{$table}{refrtable}`
check written to detect partition-by-reference tables silently
autovivifies a phantom `partitions_list` entry for *every* table that
goes through `_create_unique_keys()` — partitioned or not — because
`exists` on a multi-level hash dereference creates the intermediate
level as a side effect. `_create_foreign_keys()` later treats that
phantom entry as proof the referenced table is partitioned and skips
the constraint, but only when `$self->{pg_version} <= 12`, which is
exactly the shipped default (11) for a config that has never had
`PG_VERSION` set.

Verified directly for MSSQL rather than assumed from the MySQL result:

```sh
ora2pg -M -i schema.sql -t TABLE -o out.sql -b out          # PG_VERSION unset -> 0 FOREIGN KEY lines
ora2pg -c myconf.conf -M -i schema.sql -t TABLE -o out.sql -b out   # PG_VERSION 16 -> constraint present
```

Both `_foreign_key()` (the dialect-specific, live-query-only function
this document previously blamed) and `_create_foreign_keys()` /
`_create_unique_keys()` (the actual culprits) live in code paths shared
across MySQL, MSSQL and Oracle sources, so the fix and the trigger
condition are identical to GAP-082's: it is `PG_VERSION`, not the
dialect and not the input mode. No live SQL Server instance was
available to repeat the live-connection half of GAP-082's four-way
verification table for MSSQL specifically, but the file-input half is
directly confirmed above, and the code responsible is not MSSQL-specific
in the first place.

## Observed problem

With a config that has never had `PG_VERSION` set explicitly (or has it
set to 12 or below), the foreign key silently disappears: no error at
load or afterwards, the schema comes up, the application runs, and
referential integrity simply ceases to exist, along with the cascading
delete.

**Reproducible: YES**, with `PG_VERSION` unset or set to 12 or lower.
Ora2Pg version: 25.0, PostgreSQL 16. Source dialect: MSSQL (`ora2pg
-M`).

## Verdict

**Gap confirmed, severity high, failure_stage semantic**, conditional on
`PG_VERSION <= 12` (including the unset default). Fixed by setting
`PG_VERSION` to the real target PostgreSQL version (13 or higher)
before conversion; if the target genuinely is PostgreSQL ≤12, the
constraint has to be restored by hand: `ALTER TABLE <table> ADD
CONSTRAINT <name> FOREIGN KEY (<columns>) REFERENCES <parent>
(<columns>) ON DELETE ...` after all tables are loaded. Implemented:
`ora2pg_gap_report/detectors/mssql_foreign_key.py`.
