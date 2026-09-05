# GAP-050: `LONG RAW` converted to `text` rather than `bytea`

Oracle feature: `LONG RAW` — a legacy binary type.

## Minimal example

```sql
CREATE TABLE binstuff (
    id       NUMBER PRIMARY KEY,
    a_raw    RAW(200),
    a_long   LONG,
    a_lraw   LONG RAW,
    a_blob   BLOB,
    a_clob   CLOB,
    a_bfile  BFILE
);
```

All the types are in one example deliberately, so that `LONG RAW`'s
mapping can be compared with its neighbours' in the very same run.

## ora2pg output (v25.0, `-t TABLE`)

```sql
CREATE TABLE binstuff (
	id bigint,
	a_raw bytea,
	a_long text,
	a_lraw text,
	a_blob bytea,
	a_clob text,
	a_bfile bytea
) ;
```

`RAW(200)`, `BLOB` and `BFILE` are mapped to `bytea` correctly. `LONG RAW`
becomes `text`.

## Observed problem

This is ora2pg disagreeing with its own documentation, not a deliberate
choice. The documented default (`doc/Ora2Pg.pod`, the `DATA_TYPE`
directive) contains `LONG RAW:bytea`, and the same mapping is written in
the code — `lib/Ora2Pg/Oracle.pm:45`:

```perl
	'LONG RAW' => 'bytea',
```

The `CREATE TABLE` loads cleanly, so the problem is invisible at the
schema stage. It surfaces when the data is migrated: arbitrary bytes
cannot be stored in `text`. Confirmed against a real PostgreSQL 16 — the
same bytes into `bytea` and into `text`:

```
 bytea ok | \x00ff01fe
(1 row)

ERROR:  invalid byte sequence for encoding "UTF8": 0x00
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/long_raw_type.py`. Manual rework: change the
column's type to `bytea` — the very mapping ora2pg declares for `LONG
RAW`. Plain `LONG` (the character type) maps to `text` correctly and is
not flagged by the detector.
