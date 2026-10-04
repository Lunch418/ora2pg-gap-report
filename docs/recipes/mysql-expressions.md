*English | [Русский](mysql-expressions.ru.md)*

# MySQL expressions: LIMIT, LAST_INSERT_ID, DATE_FORMAT, ENUM, SET

Covers: GAP-075 (`mysql_limit_comma`), GAP-079 (`mysql_last_insert_id`),
GAP-081 (`mysql_date_format`), GAP-069
(`mysql_on_update_current_timestamp`), GAP-068 (`mysql_enum_type`),
GAP-086 (`mysql_set_type`).

## The problem

Six MySQL forms that `ora2pg -m` copies unchanged, mangles, or converts
halfway. Each is short to fix by hand once you know what PostgreSQL
expects.

## LIMIT offset, count

```sql
CREATE TABLE items (id integer PRIMARY KEY, name text NOT NULL);
INSERT INTO items SELECT g, 'item ' || g FROM generate_series(1, 20) AS g;

DO $$
BEGIN
    -- MySQL: SELECT id FROM items ORDER BY id LIMIT 10, 5
    ASSERT (SELECT array_agg(id) FROM (SELECT id FROM items ORDER BY id LIMIT 5 OFFSET 10) s)
           = ARRAY[11, 12, 13, 14, 15];
END $$;
```

The order of the two numbers flips: MySQL's `LIMIT 10, 5` is
`LIMIT 5 OFFSET 10`. `LIMIT 5 OFFSET 10` (MySQL also accepts that form)
needs no change.

## LAST_INSERT_ID() -> RETURNING

```sql
CREATE TABLE notes (id serial PRIMARY KEY, body text NOT NULL);

DO $$
DECLARE
    v_id integer;
BEGIN
    -- INSERT INTO notes (body) VALUES ('x'); SET v_id = LAST_INSERT_ID();
    INSERT INTO notes (body) VALUES ('x') RETURNING id INTO v_id;
    ASSERT v_id = 1;
    -- the closest drop-in, when the INSERT cannot be changed:
    ASSERT lastval() = 1;
END $$;
```

`lastval()` returns the last value any sequence produced in the session,
including one used by a trigger, and fails if none has been used yet.
`RETURNING` is exact.

## DATE_FORMAT -> to_char

`ora2pg` turns `DATE_FORMAT(d, fmt)` into a parenthesized pair without the
function name, so the query returns a row instead of a string, and leaves
some specifiers untranslated (GAP-081). Write `to_char` with PostgreSQL's
template:

```sql
DO $$
DECLARE
    d timestamp := '2026-03-07 14:05:09';
BEGIN
    -- DATE_FORMAT(d, '%Y-%m-%d %H:%i:%s')
    ASSERT to_char(d, 'YYYY-MM-DD HH24:MI:SS') = '2026-03-07 14:05:09';
    -- DATE_FORMAT(d, '%e %M %Y, %W')
    ASSERT to_char(d, 'FMDD FMMonth YYYY, FMDay') = '7 March 2026, Saturday';
    -- DATE_FORMAT(d, '%h:%i %p')
    ASSERT to_char(d, 'HH12:MI AM') = '02:05 PM';
END $$;
```

| MySQL | `to_char` | MySQL | `to_char` |
|---|---|---|---|
| `%Y` | `YYYY` | `%H` | `HH24` |
| `%y` | `YY` | `%h`, `%I` | `HH12` |
| `%m` | `MM` | `%i` | `MI` |
| `%c` | `FMMM` | `%s`, `%S` | `SS` |
| `%d` | `DD` | `%p` | `AM` |
| `%e` | `FMDD` | `%f` | `US` |
| `%M` | `FMMonth` | `%j` | `DDD` |
| `%b` | `Mon` | `%W` | `FMDay` |
| `%a` | `Dy` | `%%` | `%` |

`FM` removes the padding: without it `Month` is padded to nine
characters, the way Oracle does it. `STR_TO_DATE(s, fmt)` is `to_timestamp(s,
template)` with the same table.

## ON UPDATE CURRENT_TIMESTAMP -> a trigger

```sql
CREATE TABLE profiles (
    id         integer PRIMARY KEY,
    name       text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()   -- the DEFAULT part stays
);

CREATE FUNCTION touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- MySQL bumps the column only when the row actually changed
    IF NEW IS DISTINCT FROM OLD THEN
        NEW.updated_at := clock_timestamp();
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER profiles_touch
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

INSERT INTO profiles VALUES (1, 'old', '2000-01-01');
UPDATE profiles SET name = 'old';   -- no change: the stamp stays
DO $$
BEGIN
    ASSERT (SELECT updated_at FROM profiles) = '2000-01-01';
END $$;
UPDATE profiles SET name = 'new';
DO $$
BEGIN
    ASSERT (SELECT updated_at FROM profiles) > '2000-01-01';
END $$;
```

The function is generic: one per database, one trigger per table that had
`ON UPDATE CURRENT_TIMESTAMP`. Use `clock_timestamp()` if each row should
get the time it was really written, `now()` if all rows of a transaction
should share the transaction's start time (MySQL's behaviour is the
statement's time, between the two).

## ENUM: create the type ora2pg forgot

`ora2pg` names a type for each `ENUM` column, `<table>_<column>_t`, and
uses it in the table, but never writes the `CREATE TYPE` (GAP-068). The
smallest fix is to add exactly that statement before the table:

```sql
-- MySQL: status ENUM('new', 'paid', 'shipped') NOT NULL DEFAULT 'new'
CREATE TYPE orders_status_t AS ENUM ('new', 'paid', 'shipped');

CREATE TABLE orders (
    id     serial PRIMARY KEY,
    status orders_status_t NOT NULL DEFAULT 'new'
);
INSERT INTO orders (status) VALUES ('shipped'), ('new');

DO $$
BEGIN
    -- sorted by declaration order, as in MySQL
    ASSERT (SELECT array_agg(status::text ORDER BY status) FROM orders) = ARRAY['new', 'shipped'];
END $$;
```

Take the values from the MySQL `CREATE TABLE`; the generated file no
longer has them. Two differences from MySQL: an invalid value is an error
(MySQL in non-strict mode stores `''`), and adding a value later is
`ALTER TYPE ... ADD VALUE`, while removing one means a new type. If the
list changes often, `text` with a `CHECK (status IN (...))` is easier to
evolve.

## SET -> an array with a check

`ora2pg` makes a `SET('a','b',...)` column plain `text`, so any string is
accepted (GAP-086). An array keeps both the multiple values and the check:

```sql
CREATE TABLE posts (
    id   integer PRIMARY KEY,
    tags text[] NOT NULL DEFAULT '{}'
         CHECK (tags <@ ARRAY['news', 'tech', 'sport'])   -- SET('news','tech','sport')
);
INSERT INTO posts VALUES (1, ARRAY['news', 'tech']);

DO $$
BEGIN
    -- FIND_IN_SET('tech', tags) > 0
    ASSERT (SELECT 'tech' = ANY (tags) FROM posts WHERE id = 1);
    BEGIN
        INSERT INTO posts VALUES (2, ARRAY['gossip']);
        RAISE EXCEPTION 'an unknown value was accepted';
    EXCEPTION WHEN check_violation THEN
        NULL;  -- expected
    END;
END $$;
```

Existing data comes over as text like `'news,tech'`; convert it with
`string_to_array(value, ',')` during the load.
