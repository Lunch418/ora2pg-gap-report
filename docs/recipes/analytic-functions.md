*English | [Русский](analytic-functions.ru.md)*

# KEEP, IGNORE NULLS, WM_CONCAT and SAMPLE

Covers: GAP-040 (`keep_dense_rank`), GAP-048 (`ignore_nulls`), GAP-065
(`wm_concat`), GAP-042 (`sample_clause`).

## The problem

Four pieces of Oracle aggregate and analytic syntax that `ora2pg` copies
as they are, and PostgreSQL 16 does not accept. Each has a short
equivalent.

```sql
CREATE TABLE emp (
    emp_id    integer PRIMARY KEY,
    dept      text    NOT NULL,
    hired     date    NOT NULL,
    salary    numeric NOT NULL,
    last_name text    NOT NULL
);
INSERT INTO emp VALUES
    (1, 'sales', '2020-01-10', 3000, 'Abel'),
    (2, 'sales', '2020-01-10', 3500, 'Baer'),
    (3, 'sales', '2021-05-01', 4000, 'Chen'),
    (4, 'it',    '2019-03-15', 5000, 'Diaz');
```

## KEEP (DENSE_RANK FIRST / LAST ...)

```plsql
SELECT dept,
       MAX(salary) KEEP (DENSE_RANK FIRST ORDER BY hired) AS top_of_first_hired,
       SUM(salary) KEEP (DENSE_RANK LAST  ORDER BY hired) AS sum_of_last_hired
FROM emp
GROUP BY dept;
```

`KEEP (DENSE_RANK FIRST ORDER BY k)` means "aggregate only the rows with the
lowest `k`". For `MAX` and `MIN` an ordered `array_agg` says it in one
expression; for any aggregate, rank first and filter:

```sql
CREATE VIEW emp_keep AS
SELECT dept,
       -- MAX(salary) KEEP (DENSE_RANK FIRST ORDER BY hired):
       -- order by the KEEP key, then so the wanted value comes first
       (array_agg(salary ORDER BY hired ASC, salary DESC))[1] AS top_of_first_hired,
       -- SUM(salary) KEEP (DENSE_RANK LAST ORDER BY hired)
       sum(salary) FILTER (WHERE rnk_last = 1) AS sum_of_last_hired
FROM (
    SELECT e.*, dense_rank() OVER (PARTITION BY dept ORDER BY hired DESC) AS rnk_last
    FROM emp e
) ranked
GROUP BY dept;

DO $$
BEGIN
    ASSERT (SELECT top_of_first_hired FROM emp_keep WHERE dept = 'sales') = 3500;
    ASSERT (SELECT sum_of_last_hired FROM emp_keep WHERE dept = 'sales') = 4000;
END $$;
```

`DENSE_RANK LAST` is `FIRST` with the order reversed. The analytic form,
`MAX(salary) KEEP (DENSE_RANK FIRST ORDER BY hired) OVER (PARTITION BY
dept)`, cannot use an ordered `array_agg` (PostgreSQL does not allow
`ORDER BY` inside an aggregate used as a window function), but
`first_value` with the same ordering in the window says the same thing:

```sql
DO $$
BEGIN
    ASSERT (
        SELECT array_agg(top ORDER BY emp_id)
        FROM (
            SELECT emp_id,
                   first_value(salary) OVER (PARTITION BY dept ORDER BY hired ASC, salary DESC) AS top
            FROM emp
        ) w
    ) = ARRAY[3500, 3500, 3500, 5000]::numeric[];
END $$;
```

## IGNORE NULLS

PostgreSQL 16 has `FIRST_VALUE`, `LAST_VALUE` and `LAG`, but not the
`IGNORE NULLS` option. The most common use is carrying the last known
value forward:

```sql
CREATE TABLE readings (t integer PRIMARY KEY, value numeric);
INSERT INTO readings VALUES (1, 10), (2, NULL), (3, NULL), (4, 7), (5, NULL);

-- LAST_VALUE(value IGNORE NULLS) OVER (ORDER BY t)
CREATE VIEW readings_filled AS
SELECT t,
       value,
       first_value(value) OVER (PARTITION BY grp ORDER BY t) AS filled
FROM (
    -- count() skips NULLs: the counter only moves on a real value,
    -- so each real value and the NULLs after it share one group
    SELECT t, value, count(value) OVER (ORDER BY t) AS grp
    FROM readings
) g;

DO $$
BEGIN
    ASSERT (SELECT array_agg(filled ORDER BY t) FROM readings_filled) = ARRAY[10, 10, 10, 7, 7]::numeric[];
END $$;
```

For `FIRST_VALUE(x IGNORE NULLS) OVER (... ORDER BY o)`, sort the `NULL`s
to the end of the window so the first value is the first real one:

```sql
DO $$
BEGIN
    -- FIRST_VALUE(value IGNORE NULLS) OVER (ORDER BY t
    --     ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
    ASSERT (
        SELECT DISTINCT first_value(value) OVER (ORDER BY value IS NULL, t)
        FROM readings
    ) = 10;
END $$;
```

`RESPECT NULLS` is the default behaviour in both databases; just delete
the words.

## WM_CONCAT -> string_agg

```sql
DO $$
BEGIN
    -- WM_CONCAT(last_name): undocumented, comma-separated, no order
    ASSERT (SELECT string_agg(last_name, ',' ORDER BY last_name) FROM emp WHERE dept = 'sales') = 'Abel,Baer,Chen';
END $$;
```

`WM_CONCAT` never promised an order. Add `ORDER BY` inside `string_agg`
anyway, so the result stops changing from run to run. `LISTAGG(x, ',')
WITHIN GROUP (ORDER BY y)` is the same `string_agg(x, ',' ORDER BY y)`;
`ora2pg` converts that one itself.

## SAMPLE -> TABLESAMPLE

| Oracle | PostgreSQL |
|---|---|
| `FROM t SAMPLE (10)` | `FROM t TABLESAMPLE BERNOULLI (10)` |
| `FROM t SAMPLE BLOCK (10)` | `FROM t TABLESAMPLE SYSTEM (10)` |
| `... SEED (42)` | `... REPEATABLE (42)` |

```sql
DO $$
BEGIN
    ASSERT (SELECT count(*) FROM emp TABLESAMPLE BERNOULLI (100) REPEATABLE (42)) = 4;
    ASSERT (SELECT count(*) FROM emp TABLESAMPLE BERNOULLI (0)) = 0;
END $$;
```

Both take a percentage and both are approximate: a 10 % sample of a small
table can come back empty. `REPEATABLE` gives the same rows again only as
long as the table does not change, the same as Oracle's `SEED`.
