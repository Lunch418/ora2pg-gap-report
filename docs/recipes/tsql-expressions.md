*English | [Русский](tsql-expressions.ru.md)*

# T-SQL expressions: TOP, IIF, DATEDIFF, SCOPE_IDENTITY, OUTPUT

Covers: GAP-095 (`mssql_top_clause`), GAP-098 (`mssql_iif`), GAP-099
(`mssql_datediff`), GAP-096 (`mssql_scope_identity`), GAP-097
(`mssql_output_clause`).

## The problem

`ora2pg -M` copies these T-SQL forms as they are, and PostgreSQL rejects
each of them. Four are a direct rewrite. `DATEDIFF` is the one to slow down
for: it counts calendar boundaries, not elapsed time, and the obvious
PostgreSQL expression gives different numbers.

```sql
CREATE TABLE tickets (
    id       integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title    text NOT NULL,
    priority integer NOT NULL,
    status   text NOT NULL DEFAULT 'open'
);
INSERT INTO tickets (title, priority) VALUES ('a', 3), ('b', 1), ('c', 2), ('d', 2);
```

## TOP

| T-SQL | PostgreSQL |
|---|---|
| `SELECT TOP 2 * FROM t ORDER BY p` | `SELECT * FROM t ORDER BY p LIMIT 2` |
| `SELECT TOP (2) WITH TIES ... ORDER BY p` | `... ORDER BY p FETCH FIRST 2 ROWS WITH TIES` |
| `SELECT TOP 10 PERCENT ...` | `... LIMIT (SELECT ceil(count(*) * 0.10) FROM t)` |
| `UPDATE TOP (n) t SET ...` | `UPDATE t SET ... WHERE id IN (SELECT id FROM t ... LIMIT n)` |

```sql
DO $$
BEGIN
    ASSERT (SELECT array_agg(title) FROM (SELECT title FROM tickets ORDER BY priority, title LIMIT 2) s) = ARRAY['b', 'c'];
    ASSERT (SELECT count(*) FROM (SELECT 1 FROM tickets ORDER BY priority FETCH FIRST 2 ROWS WITH TIES) s) = 3;
END $$;
```

## IIF -> CASE

```sql
DO $$
BEGIN
    -- IIF(priority = 1, 'urgent', 'normal')
    ASSERT (SELECT CASE WHEN priority = 1 THEN 'urgent' ELSE 'normal' END
            FROM tickets WHERE title = 'b') = 'urgent';
END $$;
```

## DATEDIFF counts boundaries

`DATEDIFF(month, '2026-01-31', '2026-02-01')` is `1`: one month boundary
was crossed, although only a day passed. `DATEDIFF(year, '2025-12-31',
'2026-01-01')` is `1` too. A PostgreSQL `age()` or interval arithmetic
measures elapsed time and gives `0` for both. To keep the T-SQL results,
count boundaries the same way:

```sql
CREATE FUNCTION datediff(p_part text, p_start timestamp, p_end timestamp)
RETURNS bigint
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE lower(p_part)
        WHEN 'year'   THEN extract(year FROM p_end) - extract(year FROM p_start)
        WHEN 'month'  THEN (extract(year FROM p_end) - extract(year FROM p_start)) * 12
                           + extract(month FROM p_end) - extract(month FROM p_start)
        WHEN 'day'    THEN p_end::date - p_start::date
        WHEN 'hour'   THEN extract(epoch FROM date_trunc('hour', p_end) - date_trunc('hour', p_start)) / 3600
        WHEN 'minute' THEN extract(epoch FROM date_trunc('minute', p_end) - date_trunc('minute', p_start)) / 60
        WHEN 'second' THEN extract(epoch FROM date_trunc('second', p_end) - date_trunc('second', p_start))
    END::bigint
$$;

DO $$
BEGIN
    ASSERT datediff('month', '2026-01-31', '2026-02-01') = 1;
    ASSERT datediff('year', '2025-12-31', '2026-01-01') = 1;
    ASSERT datediff('day', '2026-03-01 23:59', '2026-03-02 00:01') = 1;
    ASSERT datediff('hour', '2026-03-01 10:59', '2026-03-01 11:00') = 1;
    ASSERT datediff('month', '2026-03-15', '2026-01-15') = -2;   -- negative, like T-SQL
END $$;
```

The part is passed as text (`'month'`), since PostgreSQL has no bare
`month` keyword argument. If the T-SQL code actually meant elapsed time
(a duration in days for a fee, say), write it as such instead:
`p_end::date - p_start::date` for days, `extract(epoch FROM p_end -
p_start)` for seconds.

## SCOPE_IDENTITY, @@IDENTITY -> RETURNING

```sql
DO $$
DECLARE
    v_id integer;
BEGIN
    -- INSERT INTO tickets (...) VALUES (...); SET @id = SCOPE_IDENTITY();
    INSERT INTO tickets (title, priority) VALUES ('e', 5)
    RETURNING id INTO v_id;
    ASSERT v_id = (SELECT id FROM tickets WHERE title = 'e');
END $$;
```

`RETURNING` gives the id of exactly the row this statement inserted,
which is what `SCOPE_IDENTITY()` was for. `@@IDENTITY` (the last identity
in the session, including rows inserted by triggers) is closest to
PostgreSQL's `lastval()`, with the same trap; prefer `RETURNING`.

## OUTPUT -> RETURNING

```sql
CREATE TABLE ticket_log (ticket_id integer, old_status text, new_status text);

-- UPDATE tickets SET status = 'closed'
-- OUTPUT inserted.id, deleted.status, inserted.status INTO ticket_log
-- WHERE priority = 2;
WITH old AS (
    SELECT id, status FROM tickets WHERE priority = 2 FOR UPDATE
),
changed AS (
    UPDATE tickets t SET status = 'closed'
    FROM old
    WHERE t.id = old.id
    RETURNING t.id, old.status AS old_status, t.status AS new_status
)
INSERT INTO ticket_log SELECT * FROM changed;

DO $$
BEGIN
    ASSERT (SELECT count(*) FROM ticket_log WHERE old_status = 'open' AND new_status = 'closed') = 2;
END $$;
```

| T-SQL | PostgreSQL |
|---|---|
| `INSERT ... OUTPUT inserted.*` | `INSERT ... RETURNING *` |
| `DELETE ... OUTPUT deleted.*` | `DELETE ... RETURNING *` |
| `UPDATE ... OUTPUT inserted.col` | `UPDATE ... RETURNING col` |
| `UPDATE ... OUTPUT deleted.col` (the old value) | join the old row in, as above |
| `... OUTPUT ... INTO log_table` | `WITH x AS (... RETURNING ...) INSERT INTO log_table SELECT * FROM x` |

In PostgreSQL 16 `RETURNING` sees only the new row, so the old value comes
from a locked read of the same rows (`FOR UPDATE` keeps a concurrent
change from slipping in between). PostgreSQL 18 adds `RETURNING OLD.col`.
