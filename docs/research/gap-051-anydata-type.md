# GAP-051: `SYS.ANYDATA` as a column type

Oracle feature: `ANYDATA` / `ANYDATASET` / `ANYTYPE` — a self-describing
container holding a value of any type together with information about the
type itself.

## Minimal example

```sql
CREATE TABLE settings (
    id  NUMBER PRIMARY KEY,
    val SYS.ANYDATA
);
```

## ora2pg output (v25.0, `-t TABLE`)

```sql
CREATE TABLE settings (
	id bigint,
	val SYS.ANYDATA
) ;
```

The type name is carried over as written, `SYS` schema included.

## Observed problem

Confirmed against a real PostgreSQL 16:

```
ERROR:  schema "sys" does not exist
LINE 3:  val SYS.ANYDATA
             ^
```

For the short spelling (`ANYDATA` with no prefix) the error is about a
non-existent type instead. Either way it fails immediately, at DDL load.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/anydata_type.py`. Manual rework: there is no
mechanical substitution — the column is usually remodelled as `jsonb` (if
storing an arbitrary structure matters) or split into several typed
columns with a discriminator, if only two or three concrete variants were
really being stored.
