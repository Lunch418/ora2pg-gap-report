*English | [Русский](temporary-tables.ru.md)*

# Global temporary tables

Covers: GAP-012 (`global_temp_table`), GAP-111 (`mysql_temporary_table`).

## The problem

Two different things share the word "temporary".

An Oracle **global temporary table** is a permanent schema object: created
once, visible to every session, with each session seeing only its own rows,
cleared at `COMMIT` by default (`ON COMMIT DELETE ROWS`). `ora2pg` turns it
into `CREATE TEMPORARY TABLE` and drops the `ON COMMIT` clause (GAP-012).
That breaks it twice:

- PostgreSQL's default is the opposite, `ON COMMIT PRESERVE ROWS`, so rows
  outlive the commit that Oracle would have cleared them at.
- A PostgreSQL temporary table exists only in the session that created it.
  Run the generated DDL once at deployment and the table is there for the
  deploying session only; every application session that uses it gets
  `relation "..." does not exist`.

A MySQL `CREATE TEMPORARY TABLE`, on the other hand, is already created at
run time by the session that uses it. `ora2pg` drops the `TEMPORARY` and
makes it a permanent table shared by everyone (GAP-111): keep the keyword.

## Pattern: create it in the session that uses it

Replace the DDL with a function that creates the table if this session
does not have it yet, and call it before the first use:

```sql
CREATE FUNCTION staging_orders_ensure()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    CREATE TEMPORARY TABLE IF NOT EXISTS staging_orders (
        order_id integer PRIMARY KEY,
        amount   numeric NOT NULL
    ) ON COMMIT DELETE ROWS;   -- Oracle's default; PRESERVE ROWS if the GTT said so
END;
$$;

CREATE FUNCTION staging_orders_total()
RETURNS numeric
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM staging_orders_ensure();
    INSERT INTO staging_orders VALUES (1, 10), (2, 32);
    RETURN (SELECT sum(amount) FROM staging_orders);
END;
$$;

DO $$
BEGIN
    ASSERT staging_orders_total() = 42;
    -- a second call in the same session must not fail on the existing table
    PERFORM staging_orders_ensure();
    ASSERT (SELECT relpersistence FROM pg_class WHERE oid = 'staging_orders'::regclass) = 't';
END $$;
```

Notes on the pattern:

- `IF NOT EXISTS` makes the call cheap after the first one (a notice, no
  error). Raise `client_min_messages` to `warning` if the notice is noise.
- Indexes go inside the function too, right after the table; they are as
  temporary as the table.
- A temporary table is invisible to other sessions, which is exactly the
  Oracle behaviour; there is nothing to `GRANT`.
- Never put `CREATE TEMPORARY TABLE` for an Oracle GTT in the deployment
  script. It succeeds and hides the problem until the first real session.

## ON COMMIT, side by side

| Oracle | PostgreSQL |
|---|---|
| `ON COMMIT DELETE ROWS`, or no `ON COMMIT` at all | `ON COMMIT DELETE ROWS` (must be written out) |
| `ON COMMIT PRESERVE ROWS` | `ON COMMIT PRESERVE ROWS`, or nothing (the default) |
| (session ends) | the table and its rows disappear |

`ON COMMIT DROP` also exists in PostgreSQL; it removes the table itself at
commit and has no Oracle counterpart.

## When the table is used heavily

Creating a temporary table touches the system catalogs. Code that creates
and drops them thousands of times a minute bloats `pg_class` and
`pg_attribute`. Two ways out:

- the `pgtt` extension, which emulates Oracle-style global temporary
  tables (one definition, per-session rows) on top of PostgreSQL;
- an ordinary **unlogged** table with a session key column, filled and
  cleared explicitly:

```sql
CREATE UNLOGGED TABLE staging_orders_shared (
    session_pid integer NOT NULL DEFAULT pg_backend_pid(),
    order_id    integer NOT NULL,
    amount      numeric NOT NULL,
    PRIMARY KEY (session_pid, order_id)
);

CREATE VIEW staging_orders_mine AS
    SELECT order_id, amount FROM staging_orders_shared WHERE session_pid = pg_backend_pid();

INSERT INTO staging_orders_shared (order_id, amount) VALUES (1, 5);
DO $$
BEGIN
    ASSERT (SELECT sum(amount) FROM staging_orders_mine) = 5;
END $$;
-- what ON COMMIT DELETE ROWS did for you, done by hand:
DELETE FROM staging_orders_shared WHERE session_pid = pg_backend_pid();
```

With the shared table, rows left by a session that crashed stay behind;
clean up rows whose `session_pid` is no longer in `pg_stat_activity`
periodically.

## MySQL temporary tables

MySQL code creates its temporary tables at run time already. Keep the
statement where it is and keep the keyword:

```sql
CREATE TEMPORARY TABLE IF NOT EXISTS report_rows (
    id    integer,
    label text
);  -- MySQL: rows live for the session, which is PostgreSQL's default too
```
