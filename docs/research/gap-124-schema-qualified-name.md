# GAP-124: a schema-qualified name keeps its schema, which is never created

Oracle feature: an object created under its owner's name - `CREATE TABLE
"HR"."GX_EMP"`. `DBMS_METADATA.GET_DDL` writes every name this way, so
this is what an export made with it looks like throughout.

## How it was found

`--migrate --load-check docker` on a `GET_DDL`-style export: nothing loaded
on a fresh PostgreSQL, every error `schema "hr" does not exist`.

## Minimal example

`tests/fixtures/gaps_124_125/oracle_source.sql`:

```sql
CREATE TABLE "HR"."GX_EMP" ("ID" NUMBER(6,0) NOT NULL ENABLE, CONSTRAINT "GX_EMP_PK" PRIMARY KEY ("ID"));
CREATE SEQUENCE "HR"."GX_SEQ" MINVALUE 1 START WITH 1;
CREATE OR REPLACE FORCE EDITIONABLE VIEW "HR"."GX_V" ("ID") AS SELECT id FROM gx_emp;
CREATE OR REPLACE EDITIONABLE TRIGGER "HR"."GX_TRG" BEFORE INSERT ON "HR"."GX_EMP" FOR EACH ROW
BEGIN
  NULL;
END;
/
```

with a package `"HR"."GX_PKG"` as well. In a live Oracle 23ai (as `HR`)
every object is VALID, an insert fires the trigger and the view sees the
row.

## ora2pg output (v25.0)

```sql
CREATE TABLE hr.gx_emp (...);
ALTER TABLE hr.gx_emp ADD PRIMARY KEY (id);
CREATE SEQUENCE hr.gx_seq INCREMENT 1 MINVALUE 1 NO MAXVALUE START 1;
CREATE OR REPLACE VIEW hr.gx_v (id) AS SELECT id FROM gx_emp;
CREATE TRIGGER gx_trg
	BEFORE INSERT ON gx_emp FOR EACH ROW
	EXECUTE PROCEDURE trigger_fct_gx_trg();
```

The schema stays on tables, sequences, views and routines and is dropped
from a trigger's `ON` and from a view's body. There is no `CREATE SCHEMA
hr` anywhere. (A package is not affected: ora2pg turns it into a schema of
its own name and creates that one.)

## Observed problem

On a fresh PostgreSQL 16:

```
ERROR:  3F000: schema "hr" does not exist
```

for the table, the sequence and the view. With `CREATE SCHEMA hr` run
first, the trigger and the view still fail, because they lost the schema:

```
ERROR:  42P01: relation "gx_emp" does not exist
```

With the schema created **and** on the search_path (`SET search_path = hr,
public`) everything loads and behaves as in Oracle
(`tests/test_gaps_124_125_load.py`).

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Either create
the schema and put it on the search_path for good (`ALTER ROLE app SET
search_path = hr, public` or the same on the database), or remove the
`"HR".` qualifiers from the source before ora2pg, so everything lands in
one schema consistently. Which one is a decision about where the objects
should live, so `--fix` does not make it.

Implemented: `ora2pg_gap_report/detectors/schema_qualified_name.py` -
reported once per schema per file; a schema the file creates itself is
not reported, which keeps ora2pg's own package output clean.
