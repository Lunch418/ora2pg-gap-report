# GAP-088: `NEWID()` — `uuid_generate_v4()` without the extension

MSSQL feature: `NEWID()` / `NEWSEQUENTIALID()` — GUID generation as a
default.

## Minimal example

```sql
CREATE TABLE tokens (
    id uniqueidentifier NOT NULL DEFAULT NEWID(),
    label varchar(50) NULL
);
```

## ora2pg output (v25.0, `-M -t TABLE`)

```sql
CREATE TABLE tokens (
	id uuid NOT NULL DEFAULT uuid_generate_v4(),
	label citext
) ;
```

The target is chosen correctly — `uuid` and `uuid_generate_v4()` — but
there is no `CREATE EXTENSION IF NOT EXISTS "uuid-ossp"` line in the
output.

## Observed problem

Confirmed on a real PostgreSQL 16:

```
ERROR:  function uuid_generate_v4() does not exist
```

`CREATE TABLE` fails immediately, at schema load.

Tellingly, ora2pg does have a mechanism for enabling extensions, and it
works in that very same run: for string types it emits, as the first
line,

```sql
CREATE EXTENSION IF NOT EXISTS citext;
```

So it is not that the mechanism is missing, but that it is not applied to
`uuid-ossp`. The related situation on the Oracle side is GAP-067
(`SDO_GEOMETRY` without `CREATE EXTENSION postgis`).

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed, severity high.** Fixed with a single `CREATE EXTENSION
IF NOT EXISTS "uuid-ossp"` line before loading the schema; on PostgreSQL
13+ one can instead switch to the built-in `gen_random_uuid()` and skip
the extension entirely. Severity here is high rather than medium (as with
GAP-067) because, unlike PostGIS, this is not "install an extra external
extension for an unusual data type" but a blocked load on a completely
ordinary identifier column. Implemented:
`ora2pg_gap_report/detectors/mssql_newid_default.py`.
