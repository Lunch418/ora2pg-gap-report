*English | [Русский](collections-and-bulk.ru.md)*

# Collections and bulk operations: arrays and set-based SQL

Covers: GAP-003 (`bulk_collect`), GAP-021 (`collection_type`), GAP-041
(`multiset_operator`), GAP-054 (`table_collection`).

## The problem

PL/SQL collections (`TABLE OF`, `VARRAY`, `INDEX BY`) and the bulk
statements built on them (`BULK COLLECT INTO`, `FORALL`) have no
PL/pgSQL counterpart, and `ora2pg` copies them as they are: the body
fails to compile (GAP-003). A schema-level `CREATE TYPE ... AS TABLE OF`
disappears without a trace, and every table that used it fails to load
(GAP-021). `TABLE(collection)`, `MULTISET`, `MEMBER OF` and
`SUBMULTISET OF` are copied unchanged (GAP-054, GAP-041).

In PostgreSQL the same jobs are done by two things: **plain SQL over the
whole set** where the collection was only a way to batch rows, and
**arrays** where the collection really is a value.

## First choice: no collection at all

Most `BULK COLLECT` + `FORALL` code exists because row-by-row PL/SQL was
slow. The Oracle original:

```plsql
DECLARE
    TYPE t_ids IS TABLE OF orders.order_id%TYPE;
    v_ids t_ids;
BEGIN
    SELECT order_id BULK COLLECT INTO v_ids
    FROM orders WHERE status = 'CLOSED';

    FORALL i IN 1 .. v_ids.COUNT
        INSERT INTO orders_archive SELECT * FROM orders WHERE order_id = v_ids(i);
    FORALL i IN 1 .. v_ids.COUNT
        DELETE FROM orders WHERE order_id = v_ids(i);
END;
```

In PostgreSQL, one statement does both, atomically, and is faster than any
loop:

```sql
CREATE TABLE orders (
    order_id integer PRIMARY KEY,
    status   text NOT NULL,
    amount   numeric NOT NULL
);
CREATE TABLE orders_archive (LIKE orders);
INSERT INTO orders VALUES (1, 'OPEN', 10), (2, 'CLOSED', 20), (3, 'CLOSED', 30);

CREATE PROCEDURE archive_closed_orders()
LANGUAGE sql
AS $$
    WITH moved AS (
        DELETE FROM orders WHERE status = 'CLOSED'
        RETURNING *
    )
    INSERT INTO orders_archive SELECT * FROM moved;
$$;

CALL archive_closed_orders();

DO $$
BEGIN
    ASSERT (SELECT count(*) FROM orders) = 1;
    ASSERT (SELECT sum(amount) FROM orders_archive) = 50;
END $$;
```

`DELETE ... RETURNING` inside a `WITH` hands the deleted rows to the
`INSERT`: no variable, no loop, no second scan.

## When the collection is a value: arrays

When the code really needs the list in a variable (it is passed on,
inspected, built up in a loop), use an array:

```sql
CREATE FUNCTION closed_order_ids()
RETURNS integer[]
LANGUAGE plpgsql
AS $$
DECLARE
    v_ids integer[];          -- TYPE t_ids IS TABLE OF ...; v_ids t_ids;
BEGIN
    SELECT array_agg(order_id ORDER BY order_id)   -- BULK COLLECT INTO
    INTO v_ids
    FROM orders_archive;

    IF cardinality(v_ids) > 0 THEN                 -- v_ids.COUNT
        RAISE NOTICE 'first %, last %',
            v_ids[1],                              -- v_ids(1), v_ids.FIRST
            v_ids[cardinality(v_ids)];             -- v_ids(v_ids.LAST)
    END IF;

    v_ids := v_ids || 99;                          -- v_ids.EXTEND; v_ids(v_ids.LAST) := 99
    RETURN v_ids;
END;
$$;

CREATE PROCEDURE reopen(p_ids integer[])
LANGUAGE plpgsql
AS $$
BEGIN
    -- FORALL i IN 1 .. p_ids.COUNT UPDATE ... WHERE order_id = p_ids(i)
    UPDATE orders_archive SET status = 'REOPENED' WHERE order_id = ANY (p_ids);
END;
$$;

CALL reopen(closed_order_ids());

DO $$
BEGIN
    ASSERT closed_order_ids() = ARRAY[2, 3, 99];
    ASSERT (SELECT count(*) FROM orders_archive WHERE status = 'REOPENED') = 2;
END $$;
```

| PL/SQL | PL/pgSQL |
|---|---|
| `TYPE t IS TABLE OF x` / `VARRAY(n) OF x` | `x[]` |
| `BULK COLLECT INTO v` | `SELECT array_agg(col ORDER BY ...) INTO v` |
| `v.COUNT` | `cardinality(v)` (0 for an empty array; `NULL` array gives `NULL`) |
| `v(i)` | `v[i]` (1-based, like PL/SQL) |
| `v.FIRST` / `v.LAST` | `array_lower(v, 1)` / `array_upper(v, 1)` |
| `v.EXTEND; v(v.LAST) := x` | `v := v \|\| x` |
| `v.DELETE` | `v := '{}'` |
| `FORALL i IN ... DML ... v(i)` | one DML statement with `= ANY (v)` or `unnest(v)` |
| `FOR i IN 1 .. v.COUNT LOOP` | `FOREACH x IN ARRAY v LOOP` |
| `TABLE OF orders%ROWTYPE` | `orders[]`, filled with `array_agg(o)` from `orders o` |

`array_agg` over no rows returns `NULL`, not an empty array. Write
`coalesce(array_agg(...), '{}')` where the code goes on to `cardinality`
and compares the result with `0`.

## Schema-level collection types

`CREATE TYPE phone_list AS VARRAY(3) OF varchar2(20)` becomes a domain over
an array, which keeps the size limit Oracle enforced:

```sql
CREATE DOMAIN phone_list AS varchar(20)[]
    CHECK (cardinality(VALUE) <= 3);

CREATE TABLE customers (
    customer_id integer PRIMARY KEY,
    phones      phone_list
);
INSERT INTO customers VALUES (1, ARRAY['+1 555 0100', '+1 555 0101']);

DO $$
BEGIN
    BEGIN
        INSERT INTO customers VALUES (2, ARRAY['1', '2', '3', '4']);
        RAISE EXCEPTION 'the size limit did not hold';
    EXCEPTION WHEN check_violation THEN
        NULL;  -- expected: VARRAY(3) allows at most three
    END;
END $$;
```

A nested table (`AS TABLE OF`) has no size limit: a plain array type
(`varchar(20)[]`) is enough. If the column is queried by its elements,
consider a child table instead, which PostgreSQL can index and join.

## TABLE(), MULTISET, MEMBER OF

```sql
DO $$
DECLARE
    a integer[] := ARRAY[1, 2, 2, 3];
    b integer[] := ARRAY[3, 4];
BEGIN
    -- SELECT column_value FROM TABLE(a)
    ASSERT (SELECT sum(x) FROM unnest(a) AS t(x)) = 8;
    -- a MULTISET UNION b
    ASSERT a || b = ARRAY[1, 2, 2, 3, 3, 4];
    -- a MULTISET UNION DISTINCT b
    ASSERT (SELECT array_agg(DISTINCT x ORDER BY x) FROM unnest(a || b) AS t(x)) = ARRAY[1, 2, 3, 4];
    -- a MULTISET INTERSECT b
    ASSERT (SELECT array_agg(x) FROM (SELECT unnest(a) INTERSECT ALL SELECT unnest(b)) AS t(x)) = ARRAY[3];
    -- 2 MEMBER OF a
    ASSERT 2 = ANY (a);
    -- b SUBMULTISET OF a  (as sets: ignores how many times a value repeats)
    ASSERT NOT (b <@ a);
    ASSERT ARRAY[2, 3] <@ a;
    -- CAST(MULTISET(SELECT ...) AS t)
    ASSERT ARRAY(SELECT g FROM generate_series(1, 3) AS g) = ARRAY[1, 2, 3];
END $$;
```

`<@` compares as sets: `ARRAY[2, 2, 2] <@ ARRAY[2]` is true, while Oracle's
`SUBMULTISET OF` counts repeats. When the counts matter, compare with
`EXCEPT ALL` instead: the left side is a submultiset when
`SELECT unnest(left) EXCEPT ALL SELECT unnest(right)` returns no rows.

## Associative arrays (INDEX BY)

- `INDEX BY VARCHAR2`: a `jsonb` object (`v := v || jsonb_build_object(k, x)`,
  `v ->> k`), or `hstore` for text-only values.
- `INDEX BY PLS_INTEGER` used as a sparse array: a `jsonb` object keyed by
  the number, or a temporary table when it holds many rows.
- `INDEX BY PLS_INTEGER` filled from 1 without gaps: a plain array.

## Watch out for

- **Large `BULK COLLECT ... LIMIT n` loops.** They batch to save memory.
  The set-based rewrite needs no batching; if a step must stay batched (it
  calls something per row), loop over a cursor with `FOR r IN SELECT ...`,
  which PostgreSQL already fetches in batches.
- **`SAVE EXCEPTIONS`.** `FORALL ... SAVE EXCEPTIONS` keeps going after a
  failed row. PostgreSQL has no direct equivalent: either validate first
  and DML the valid rows, or loop with an `EXCEPTION` block per row (slower).
