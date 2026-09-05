# GAP-021: `CREATE TYPE ... TABLE OF` / `VARRAY OF` — the collection type disappears without trace

Oracle feature: a collection type (`TABLE OF` — a nested table, `VARRAY(n)
OF` — a varray) declared at schema level and then used as a column type in
an ordinary table. (A local `TYPE ... IS TABLE OF` inside PL/SQL is a
separate case, already covered by GAP-003/`bulk_collect.py`; this is about
a standalone type declaration at schema level.)

## Minimal example

```sql
CREATE TYPE phone_list_t AS TABLE OF VARCHAR2(20);
/
CREATE TABLE customers (
    customer_id NUMBER,
    phones      phone_list_t
)
NESTED TABLE phones STORE AS phones_store;
```

## ora2pg output (v25.0, `-t TABLE`)

```
[DEBUG] unhandled line: CREATE TYPE phone_list_t AS TABLE OF VARCHAR2(20);
```

```sql
CREATE TABLE customers (
	customer_id bigint,
	phones PHONE_LIST_T
) ;
```

The `CREATE TYPE` never appears in the output at all — not even as an
`-- Unsupported` comment, the way object types do (see GAP-009), but
entirely, with no trace beyond a **DEBUG**-level line in the log. Yet the
`phones` column in the generated table still references the type
`phone_list_t`, which was never created.

## Observed problem

Confirmed against a real PostgreSQL 16 — loading the generated `CREATE
TABLE` fails immediately:

```
ERROR:  type "phone_list_t" does not exist
LINE 3:  phones PHONE_LIST_T
                ^
```

This is the fastest gap in the registry to surface — the error happens at
DDL load time, not on the first procedure call as with most of the other
findings, where `check_function_bodies = false` defers it. Checked
separately: `VARRAY(n) OF` behaves identically — it disappears completely
too, and produces the same class of error when the dependent table loads.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/collection_type.py`. Kept separate from
GAP-009 (`object_type.py`, which covers only `AS OBJECT`/`TYPE BODY`) —
these are different flavours of `CREATE TYPE` with different failure
modes.
