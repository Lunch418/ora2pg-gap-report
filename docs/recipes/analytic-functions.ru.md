*[English](analytic-functions.md) | Русский*

# KEEP, IGNORE NULLS, WM_CONCAT и SAMPLE

Покрывает: GAP-040 (`keep_dense_rank`), GAP-048 (`ignore_nulls`), GAP-065
(`wm_concat`), GAP-042 (`sample_clause`).

## Проблема

Четыре куска синтаксиса агрегатов и аналитических функций Oracle, которые
`ora2pg` копирует как есть, а PostgreSQL 16 не принимает. У каждого есть
короткий аналог.

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

`KEEP (DENSE_RANK FIRST ORDER BY k)` значит "агрегировать только строки с
наименьшим `k`". Для `MAX` и `MIN` это одно выражение с упорядоченным
`array_agg`; для любого агрегата - сначала ранжировать, потом
отфильтровать:

```sql
CREATE VIEW emp_keep AS
SELECT dept,
       -- MAX(salary) KEEP (DENSE_RANK FIRST ORDER BY hired):
       -- сортировка по ключу KEEP, затем так, чтобы нужное значение было первым
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

`DENSE_RANK LAST` - это `FIRST` с обратным порядком. Аналитическую форму,
`MAX(salary) KEEP (DENSE_RANK FIRST ORDER BY hired) OVER (PARTITION BY
dept)`, упорядоченным `array_agg` не записать (PostgreSQL не разрешает
`ORDER BY` внутри агрегата, используемого как оконная функция), но
`first_value` с той же сортировкой окна говорит то же самое:

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

В PostgreSQL 16 есть `FIRST_VALUE`, `LAST_VALUE` и `LAG`, но нет параметра
`IGNORE NULLS`. Чаще всего его используют, чтобы протянуть последнее
известное значение вперёд:

```sql
CREATE TABLE readings (t integer PRIMARY KEY, value numeric);
INSERT INTO readings VALUES (1, 10), (2, NULL), (3, NULL), (4, 7), (5, NULL);

-- LAST_VALUE(value IGNORE NULLS) OVER (ORDER BY t)
CREATE VIEW readings_filled AS
SELECT t,
       value,
       first_value(value) OVER (PARTITION BY grp ORDER BY t) AS filled
FROM (
    -- count() пропускает NULL: счётчик сдвигается только на настоящем значении,
    -- поэтому каждое значение и идущие за ним NULL попадают в одну группу
    SELECT t, value, count(value) OVER (ORDER BY t) AS grp
    FROM readings
) g;

DO $$
BEGIN
    ASSERT (SELECT array_agg(filled ORDER BY t) FROM readings_filled) = ARRAY[10, 10, 10, 7, 7]::numeric[];
END $$;
```

Для `FIRST_VALUE(x IGNORE NULLS) OVER (... ORDER BY o)` отправьте `NULL` в
конец окна, тогда первым будет первое настоящее значение:

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

`RESPECT NULLS` - поведение по умолчанию в обеих базах; эти слова просто
удалите.

## WM_CONCAT -> string_agg

```sql
DO $$
BEGIN
    -- WM_CONCAT(last_name): недокументированная, через запятую, без порядка
    ASSERT (SELECT string_agg(last_name, ',' ORDER BY last_name) FROM emp WHERE dept = 'sales') = 'Abel,Baer,Chen';
END $$;
```

`WM_CONCAT` никогда не обещала порядка. Всё равно добавьте `ORDER BY`
внутрь `string_agg`, чтобы результат перестал меняться от запуска к
запуску. `LISTAGG(x, ',') WITHIN GROUP (ORDER BY y)` - это тот же
`string_agg(x, ',' ORDER BY y)`; его `ora2pg` конвертирует сам.

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

Оба принимают процент и оба приблизительны: выборка 10 % из маленькой
таблицы может оказаться пустой. `REPEATABLE` возвращает те же строки только
пока таблица не меняется - так же, как `SEED` в Oracle.
