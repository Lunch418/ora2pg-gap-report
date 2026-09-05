# GAP-104: a computed column gets the type `citext`

MSSQL feature: a computed column — `<name> AS (<expression>)`, with or
without `PERSISTED`.

## Minimal example

```sql
CREATE TABLE items3 (
    id int NOT NULL PRIMARY KEY,
    price decimal(10,2) NOT NULL,
    qty int NOT NULL,
    total AS (price * qty) PERSISTED
);
```

## ora2pg output (v25.0, `-M -t TABLE`)

```sql
CREATE TABLE items3 (
	id integer NOT NULL,
	price numeric(10,2) NOT NULL,
	qty integer NOT NULL,
	total citext
) ;
...
CREATE OR REPLACE FUNCTION fct_virt_col_items3_trigger() RETURNS trigger AS $BODY$
BEGIN
	NEW.total = (NEW.price * NEW.qty) PERSISTED;

RETURN NEW;
end
$BODY$
 LANGUAGE 'plpgsql' SECURITY DEFINER;
```

The trigger approach itself works, but the column type came out as
`citext` — regardless of what the expression computes. The keyword
`PERSISTED` also made it into the trigger body.

## Observed problem

No error at load or on insert. Verified on a real PostgreSQL 16:

```
=# \d items3
 Column |     Type      | Nullable
--------+---------------+----------
 id     | integer       | not null
 price  | numeric(10,2) | not null
 qty    | integer       | not null
 total  | citext        |
```

The value is computed and stored, but from then on it is a string:
sorting is lexicographic (`'100' < '20'`), and comparison against a
number or `SUM()` over the column either fails or returns the wrong
thing.

The word `PERSISTED` in the trigger body, oddly enough, causes no error:
PostgreSQL reads it as a column alias in the expression — exactly the
same harmless accident as with `STORED` on the MySQL side.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Verdict

**Gap confirmed, severity high, failure_stage semantic.** Fixed by
changing the column to the type the expression actually computes, or
better, by moving to the built-in `GENERATED ALWAYS AS (...) STORED`,
which PostgreSQL has and which does exactly what `PERSISTED` does in SQL
Server. Implemented:
`ora2pg_gap_report/detectors/mssql_computed_column.py`.
