# GAP-031: `DEFAULT ON NULL` copied verbatim — a syntax error

Oracle feature (12c+): `<column> <type> DEFAULT ON NULL <expr>` — different
from an ordinary `DEFAULT`: a plain `DEFAULT` applies only when the column
is not mentioned in the `INSERT` at all, while `DEFAULT ON NULL` also
applies when the column is named explicitly but `NULL` is passed. Typical
for columns such as "status" or "retry count", where the application may
pass `NULL` by mistake — or deliberately, to keep the calling code uniform
— instead of an explicit value.

## Minimal example

```sql
CREATE TABLE orders (
    order_id NUMBER,
    status VARCHAR2(20) DEFAULT ON NULL 'PENDING'
);
```

## ora2pg output (v25.0, `-t TABLE`)

```sql
CREATE TABLE orders (
	order_id bigint,
	status varchar(20) DEFAULT ON NULL 'PENDING'
) ;
```

The `ON NULL` clause is copied into the output as written — PostgreSQL
does not support that syntax on `DEFAULT` at all. (In PostgreSQL 16 the
only ways to get similar behaviour are a `BEFORE` trigger or `GENERATED
ALWAYS AS ... STORED` with `COALESCE`, not `DEFAULT` itself.)

## Observed problem

Unlike most gaps in this registry, this is not a silent loss of behaviour
but an immediate failure while applying the DDL itself. Confirmed against
a real PostgreSQL 16:

```sql
CREATE TABLE orders (
	order_id bigint,
	status varchar(20) DEFAULT ON NULL 'PENDING'
) ;
-- ERROR:  syntax error at or near "ON"
-- LINE 3:  status varchar(20) DEFAULT ON NULL 'PENDING'
--                              ^
```

The migration script stops at this very table — not later, on the first
insert, as with most of the other "silent" gaps, but at once. Easy to
notice on the first run of the generated dump, but it requires a manual
rewrite to a trigger or a `COALESCE` in `GENERATED ALWAYS AS` before the
migration can get past this table.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/default_on_null.py`.
