# GAP-067: `SDO_GEOMETRY` without `CREATE EXTENSION postgis`

Oracle feature: `SDO_GEOMETRY` — the Oracle Spatial geometry type.

## Minimal example

```sql
CREATE TABLE places (
    id  NUMBER PRIMARY KEY,
    geo MDSYS.SDO_GEOMETRY
);
```

## ora2pg output (v25.0, `-t TABLE`)

```sql
CREATE TABLE places (
	id bigint,
	geo geometry(GEOMETRY)
) ;
ALTER TABLE places ADD PRIMARY KEY (id);
```

The choice of target type is right: `geometry` is PostGIS's type, the
closest analogue of `SDO_GEOMETRY`. But there is no `CREATE EXTENSION
postgis` line in the output.

## Observed problem

Confirmed against a real PostgreSQL 16 with no PostGIS installed
beforehand:

```
ERROR:  type "geometry" does not exist
LINE 3:  geo geometry(GEOMETRY)
             ^
```

It is worth comparing this with the same ora2pg's behaviour for
`SYS_GUID()` in the same run, where it does add the extension itself:

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE TABLE tokens (
	id uuid DEFAULT uuid_generate_v4(),
	tag varchar(30)
) ;
```

So ora2pg does have the "emit CREATE EXTENSION" mechanism, and simply does
not apply it for PostGIS. Automatic installation of the required extension
cannot be relied on.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed, severity medium.** Implemented in
`ora2pg_gap_report/detectors/sdo_geometry.py`. The severity is lower than
for the rest of this batch deliberately: the type mapping itself is
correct, and the whole thing is fixed by one `CREATE EXTENSION postgis`
line before loading the schema — unlike the others, nothing has to be
rewritten. Migrating the values themselves is worth checking separately,
though: the coordinate model and semantics of `SDO_GEOMETRY` and PostGIS
do not match completely.
