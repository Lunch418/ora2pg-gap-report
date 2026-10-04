*English | [Русский](read-only-and-invisible.ru.md)*

# Read-only tables and views, invisible columns and indexes

Covers: GAP-026 (`read_only_table`), GAP-066 (`read_only_view`), GAP-020
(`invisible_column`), GAP-025 (`invisible_index`).

## The problem

Four Oracle guarantees that `ora2pg` drops without a word, because
PostgreSQL has no keyword for them. Nothing fails after the migration;
the guarantee is simply gone:

- `ALTER TABLE ... READ ONLY`: writes start succeeding (GAP-026).
- `CREATE VIEW ... WITH READ ONLY`: a simple PostgreSQL view is updatable
  by default, so writes through the view reach the table (GAP-066).
- An `INVISIBLE` column appears in `SELECT *` and in `INSERT` without a
  column list (GAP-020).
- An `INVISIBLE` index is used by the planner again (GAP-025).

## A read-only table: a trigger, plus privileges

Privileges alone are not enough: the owner and superusers bypass them.
Oracle's `READ ONLY` stops everyone, and so does a trigger:

```sql
CREATE TABLE rates (currency text PRIMARY KEY, rate numeric NOT NULL);
INSERT INTO rates VALUES ('EUR', 1.08);

CREATE FUNCTION forbid_writes()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'table % is read-only', TG_TABLE_NAME
        USING ERRCODE = 'read_only_sql_transaction';
END;
$$;

-- ALTER TABLE rates READ ONLY;
CREATE TRIGGER rates_read_only
    BEFORE INSERT OR UPDATE OR DELETE OR TRUNCATE ON rates
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_writes();

DO $$
BEGIN
    BEGIN
        UPDATE rates SET rate = 2;
        RAISE EXCEPTION 'the update went through';
    EXCEPTION WHEN read_only_sql_transaction THEN
        NULL;  -- expected
    END;
    ASSERT (SELECT rate FROM rates) = 1.08;
END $$;
```

`ALTER TABLE ... READ WRITE` is then `ALTER TABLE rates DISABLE TRIGGER
rates_read_only` (and `ENABLE` to switch back). Also revoke `INSERT`,
`UPDATE`, `DELETE` and `TRUNCATE` from the application roles, so the
intent is visible in the privileges too.

## A read-only view

```sql
-- CREATE VIEW eur_rate AS SELECT ... WITH READ ONLY;
CREATE VIEW eur_rate AS SELECT currency, rate FROM rates WHERE currency = 'EUR';

CREATE FUNCTION forbid_view_writes()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'view % is read-only', TG_TABLE_NAME
        USING ERRCODE = 'read_only_sql_transaction';
END;
$$;

CREATE TRIGGER eur_rate_read_only
    INSTEAD OF INSERT OR UPDATE OR DELETE ON eur_rate
    FOR EACH ROW EXECUTE FUNCTION forbid_view_writes();

DO $$
BEGIN
    BEGIN
        DELETE FROM eur_rate;
        RAISE EXCEPTION 'the delete went through';
    EXCEPTION WHEN read_only_sql_transaction THEN
        NULL;  -- expected
    END;
END $$;
```

An `INSTEAD OF` trigger takes over every write to the view, so nothing
reaches the table, for the owner as well. If granting only `SELECT` on the
view to everyone but its owner is enough for you, privileges do the job
without a trigger.

## An invisible column: a view over the table

Keep the table under another name and give the old name to a view that
leaves the column out. Programs that use `SELECT *` or `INSERT` without
a column list see exactly what they saw in Oracle; code that knows the
column uses the table.

```sql
-- CREATE TABLE customers (id ..., name ..., legacy_code ... INVISIBLE);
CREATE TABLE customers_all (
    id          integer PRIMARY KEY,
    name        text NOT NULL,
    legacy_code text
);
CREATE VIEW customers AS SELECT id, name FROM customers_all;

INSERT INTO customers VALUES (1, 'Acme');   -- no column list, as before
UPDATE customers_all SET legacy_code = 'X1' WHERE id = 1;

DO $$
BEGIN
    ASSERT (SELECT count(*) FROM information_schema.columns
            WHERE table_name = 'customers') = 2;           -- SELECT * shows two
    ASSERT (SELECT legacy_code FROM customers_all WHERE id = 1) = 'X1';
END $$;
```

A view that selects plain columns from one table is updatable in
PostgreSQL: `INSERT`, `UPDATE` and `DELETE` through it reach the table,
and the hidden column gets its default.

## An invisible index

PostgreSQL has no way to keep an index maintained while the planner
ignores it. Why it was invisible decides what to do:

- **It was being tested before a drop.** Decide now: drop it, or keep it
  as a normal index. To see the plan without it first, drop it inside a
  transaction and roll back (`BEGIN; DROP INDEX ...; EXPLAIN ...;
  ROLLBACK;`); mind that `DROP INDEX` locks the table until the rollback,
  so do it on a copy or a quiet system.
- **It was being prepared before going live.** Create it when you want the
  planner to use it. The `hypopg` extension shows whether a plan would use
  an index without creating it.
- Do not set `pg_index.indisvalid` by hand to imitate invisibility: it is
  a catalog hack the planner and `pg_dump` do not expect.
