*English | [Русский](multi-table-dml.ru.md)*

# INSERT ALL, MERGE ... DELETE and upserts

Covers: GAP-016 (`insert_all`), GAP-002 (`merge_delete_clause`), GAP-070
(`mysql_on_duplicate_key_update`), GAP-076 (`mysql_replace_into`), GAP-077
(`mysql_insert_ignore`).

## The problem

Oracle's multi-table `INSERT ALL` / `INSERT FIRST`, the `DELETE WHERE`
branch of `MERGE`, and MySQL's `ON DUPLICATE KEY UPDATE`, `REPLACE INTO`
and `INSERT IGNORE` are all copied by `ora2pg` as they are, and PostgreSQL
rejects every one. Each has a PostgreSQL form, but two of them differ in
behaviour in ways worth reading before rewriting.

```sql
CREATE TABLE new_orders   (id integer PRIMARY KEY, amount numeric NOT NULL);
CREATE TABLE small_orders (id integer PRIMARY KEY, amount numeric NOT NULL);
CREATE TABLE big_orders   (id integer PRIMARY KEY, amount numeric NOT NULL);
CREATE TABLE all_orders   (id integer PRIMARY KEY, amount numeric NOT NULL);
INSERT INTO new_orders VALUES (1, 50), (2, 500), (3, 99), (4, 100);
```

## INSERT ALL -> data-modifying WITH

```plsql
INSERT ALL
    WHEN amount < 100  THEN INTO small_orders VALUES (id, amount)
    WHEN amount >= 100 THEN INTO big_orders   VALUES (id, amount)
    WHEN 1 = 1         THEN INTO all_orders   VALUES (id, amount)
SELECT id, amount FROM new_orders;
```

Every `INTO` becomes one `INSERT` in a `WITH`, reading the same source
once:

```sql
WITH src AS (
    SELECT id, amount FROM new_orders
),
ins_small AS (
    INSERT INTO small_orders SELECT id, amount FROM src WHERE amount < 100
),
ins_big AS (
    INSERT INTO big_orders SELECT id, amount FROM src WHERE amount >= 100
)
INSERT INTO all_orders SELECT id, amount FROM src;

DO $$
BEGIN
    ASSERT (SELECT array_agg(id ORDER BY id) FROM small_orders) = ARRAY[1, 3];
    ASSERT (SELECT array_agg(id ORDER BY id) FROM big_orders) = ARRAY[2, 4];
    ASSERT (SELECT count(*) FROM all_orders) = 4;
END $$;
```

Data-modifying parts of a `WITH` always run, whether or not anything
reads them, and the whole statement is one atomic unit, like Oracle's.

## INSERT FIRST -> one branch per row

`INSERT FIRST` stops at the first `WHEN` that matches. Compute which
branch each row takes once, then insert by branch:

```plsql
INSERT FIRST
    WHEN amount < 100  THEN INTO small_orders VALUES (id, amount)
    WHEN amount < 1000 THEN INTO big_orders   VALUES (id, amount)
    ELSE                    INTO all_orders   VALUES (id, amount)
SELECT id, amount FROM new_orders;
```

```sql
TRUNCATE small_orders, big_orders, all_orders;

WITH src AS (
    SELECT id, amount,
           CASE WHEN amount < 100  THEN 1   -- the WHENs, in order
                WHEN amount < 1000 THEN 2
                ELSE 3 END AS branch
    FROM new_orders
),
b1 AS (INSERT INTO small_orders SELECT id, amount FROM src WHERE branch = 1),
b2 AS (INSERT INTO big_orders   SELECT id, amount FROM src WHERE branch = 2)
INSERT INTO all_orders SELECT id, amount FROM src WHERE branch = 3;

DO $$
BEGIN
    ASSERT (SELECT count(*) FROM small_orders) = 2;
    ASSERT (SELECT count(*) FROM big_orders) = 2;
    ASSERT (SELECT count(*) FROM all_orders) = 0;
END $$;
```

`CASE` evaluates its branches in order and stops at the first true one,
which is exactly `INSERT FIRST`.

## MERGE ... DELETE WHERE -> a second WHEN MATCHED

PostgreSQL 15 has `MERGE`, but not Oracle's `DELETE WHERE` tail on the
update branch. It has something more general: several `WHEN MATCHED`
branches with their own conditions.

```plsql
MERGE INTO stock t
USING deliveries s ON (t.item_id = s.item_id)
WHEN MATCHED THEN
    UPDATE SET t.qty = t.qty + s.qty_change
    DELETE WHERE t.qty <= 0
WHEN NOT MATCHED THEN
    INSERT (item_id, qty) VALUES (s.item_id, s.qty_change);
```

```sql
CREATE TABLE stock      (item_id integer PRIMARY KEY, qty integer NOT NULL);
CREATE TABLE deliveries (item_id integer PRIMARY KEY, qty_change integer NOT NULL);
INSERT INTO stock VALUES (1, 10), (2, 3);
INSERT INTO deliveries VALUES (1, 5), (2, -3), (3, 7);

MERGE INTO stock t
USING deliveries s ON t.item_id = s.item_id
WHEN MATCHED AND t.qty + s.qty_change <= 0 THEN
    DELETE
WHEN MATCHED THEN
    UPDATE SET qty = t.qty + s.qty_change
WHEN NOT MATCHED THEN
    INSERT (item_id, qty) VALUES (s.item_id, s.qty_change);

DO $$
BEGIN
    ASSERT (SELECT array_agg(item_id || ':' || qty ORDER BY item_id) FROM stock) = ARRAY['1:15', '3:7'];
END $$;
```

The one thing to get right: Oracle evaluates `DELETE WHERE` against the
row **after** the update. Write the condition with the new values
(`t.qty + s.qty_change <= 0`, not `t.qty <= 0`) and put the `DELETE` branch
first, since the first matching branch wins.

## MySQL: ON DUPLICATE KEY UPDATE -> ON CONFLICT DO UPDATE

```sql
CREATE TABLE counters (name text PRIMARY KEY, hits integer NOT NULL);
INSERT INTO counters VALUES ('home', 1);

-- MySQL: INSERT INTO counters VALUES ('home', 1)
--        ON DUPLICATE KEY UPDATE hits = hits + VALUES(hits);
INSERT INTO counters VALUES ('home', 1)
ON CONFLICT (name) DO UPDATE SET hits = counters.hits + EXCLUDED.hits;

DO $$
BEGIN
    ASSERT (SELECT hits FROM counters WHERE name = 'home') = 2;
END $$;
```

`VALUES(col)` becomes `EXCLUDED.col`, and a bare column in the update
becomes `table.col`. PostgreSQL needs the conflict target spelled out:
MySQL reacts to a clash on *any* unique key, PostgreSQL only on the one
named. A table with several unique keys needs a decision about which one
the statement is really about.

## MySQL: INSERT IGNORE -> ON CONFLICT DO NOTHING

```sql
-- MySQL: INSERT IGNORE INTO counters VALUES ('home', 100);
INSERT INTO counters VALUES ('home', 100) ON CONFLICT DO NOTHING;

DO $$
BEGIN
    ASSERT (SELECT hits FROM counters WHERE name = 'home') = 2;
END $$;
```

This covers duplicate keys only. MySQL's `IGNORE` also turns other errors
into warnings: a too-long string is truncated, a `NULL` into a `NOT NULL`
column becomes the type's zero value. PostgreSQL raises those as errors.
Find out whether the code relied on that before choosing this rewrite.

## MySQL: REPLACE INTO

`REPLACE` deletes the old row and inserts the new one. Columns not listed
get their defaults, and delete triggers fire. The closest single statement
updates in place instead:

```sql
CREATE TABLE settings (
    name       text PRIMARY KEY,
    value      text NOT NULL,
    changed_by text DEFAULT 'system'
);
INSERT INTO settings VALUES ('theme', 'dark', 'alice');

-- MySQL: REPLACE INTO settings (name, value) VALUES ('theme', 'light');
INSERT INTO settings (name, value) VALUES ('theme', 'light')
ON CONFLICT (name) DO UPDATE SET value = EXCLUDED.value,
                                 changed_by = EXCLUDED.changed_by;

DO $$
BEGIN
    -- EXCLUDED.changed_by is the default, as REPLACE would have left it
    ASSERT (SELECT value || '/' || changed_by FROM settings) = 'light/system';
END $$;
```

Setting every column from `EXCLUDED`, including the ones the statement did
not list, reproduces `REPLACE`'s "unlisted columns get their defaults".
What it does not reproduce is the delete: `ON DELETE` triggers and
`ON DELETE CASCADE` children are not touched. When those matter, write the
`DELETE` and the `INSERT` as two statements in one transaction.
