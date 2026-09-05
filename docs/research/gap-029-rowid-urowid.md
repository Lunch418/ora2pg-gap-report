# GAP-029: `ROWID`/`UROWID` converted to `oid` — an incompatible type

Oracle feature: `ROWID` — a type holding a row's physical address (a
base64-like string such as `AAAWJ0AABAAAKgaAAA`); `UROWID` — its wider
variant (a logical rowid, for index-organized tables and external data).
Both are regularly used as a column type — for example to store a row
reference obtained via `SELECT ROWID ...` in audit or staging tables.

## Minimal example

```sql
CREATE TABLE orders (
    order_id NUMBER,
    row_ref  ROWID
);
```

## ora2pg output (v25.0, `-t TABLE`)

```sql
CREATE TABLE orders (
	order_id bigint,
	row_ref oid
) ;
```

`ROWID` is converted to `oid`. Also checked for `UROWID(4000)` — the same
result, `oid`.

## Observed problem

The `CREATE TABLE` runs without errors. The problem shows up on trying to
write a real value into the column — the very thing a column of this type
existed for:

```sql
INSERT INTO orders VALUES (1, 'AAAWJ0AABAAAKgaAAA');
-- ERROR:  invalid input syntax for type oid: "AAAWJ0AABAAAKgaAAA"
```

`oid` in PostgreSQL is a 4-byte integer used by the system catalogs for
internal object identifiers (and since PostgreSQL 12, `WITH OIDS` for user
tables has been removed altogether). It has nothing in common with
Oracle's ROWID representation in either format or semantics — this is not
a less precise substitute type, it is a type incompatible with the data it
is supposed to hold. Any real ROWID string — from an export, a log, or an
external system referencing an Oracle row — will fail on `INSERT`.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/rowid_type.py`.
