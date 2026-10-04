*[English](tsql-expressions.md) | Русский*

# Выражения T-SQL: TOP, IIF, DATEDIFF, SCOPE_IDENTITY, OUTPUT

Покрывает: GAP-095 (`mssql_top_clause`), GAP-098 (`mssql_iif`), GAP-099
(`mssql_datediff`), GAP-096 (`mssql_scope_identity`), GAP-097
(`mssql_output_clause`).

## Проблема

`ora2pg -M` копирует эти формы T-SQL как есть, и PostgreSQL отвергает
каждую. Четыре переписываются напрямую. На `DATEDIFF` стоит притормозить:
он считает границы календаря, а не прошедшее время, и очевидное выражение
в PostgreSQL даёт другие числа.

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

## DATEDIFF считает границы

`DATEDIFF(month, '2026-01-31', '2026-02-01')` равен `1`: пересечена одна
граница месяца, хотя прошёл всего день. `DATEDIFF(year, '2025-12-31',
'2026-01-01')` тоже `1`. `age()` или арифметика интервалов в PostgreSQL
измеряют прошедшее время и для обоих случаев дают `0`. Чтобы сохранить
результаты T-SQL, считайте границы так же:

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
    ASSERT datediff('month', '2026-03-15', '2026-01-15') = -2;   -- отрицательный, как в T-SQL
END $$;
```

Часть даты передаётся текстом (`'month'`): в PostgreSQL нет голого
ключевого слова `month` в роли аргумента. Если код T-SQL на самом деле
имел в виду прошедшее время (длительность в днях для начисления, например),
так и пишите: `p_end::date - p_start::date` для дней,
`extract(epoch FROM p_end - p_start)` для секунд.

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

`RETURNING` возвращает id ровно той строки, которую вставила эта команда, -
именно для этого и был `SCOPE_IDENTITY()`. `@@IDENTITY` (последний
identity в сессии, включая строки, вставленные триггерами) ближе всего к
`lastval()` в PostgreSQL, с той же ловушкой; предпочитайте `RETURNING`.

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
| `UPDATE ... OUTPUT deleted.col` (старое значение) | присоединить старую строку, как выше |
| `... OUTPUT ... INTO log_table` | `WITH x AS (... RETURNING ...) INSERT INTO log_table SELECT * FROM x` |

В PostgreSQL 16 `RETURNING` видит только новую строку, поэтому старое
значение берётся из заблокированного чтения тех же строк (`FOR UPDATE` не
даёт параллельному изменению вклиниться между ними). В PostgreSQL 18
появился `RETURNING OLD.col`.
