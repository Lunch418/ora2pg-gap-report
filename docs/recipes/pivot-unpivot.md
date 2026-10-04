*English | [Русский](pivot-unpivot.ru.md)*

# PIVOT and UNPIVOT

Covers: GAP-008 (`pivot_clause`).

## The problem

`PIVOT` turns row values into columns and `UNPIVOT` does the reverse.
PostgreSQL has neither keyword, and `ora2pg` copies both as they are, so
the statement fails. Both have plain-SQL equivalents that are just as
short, and need no extension.

The data for this page:

```sql
CREATE TABLE sales (
    region  text    NOT NULL,
    quarter text    NOT NULL,
    amount  numeric NOT NULL
);
INSERT INTO sales VALUES
    ('north', 'Q1', 100), ('north', 'Q2', 150), ('north', 'Q2', 50),
    ('south', 'Q1', 80),  ('south', 'Q3', 120);
```

## PIVOT -> aggregates with FILTER

```plsql
SELECT *
FROM (SELECT region, quarter, amount FROM sales)
PIVOT (SUM(amount) FOR quarter IN ('Q1' AS q1, 'Q2' AS q2, 'Q3' AS q3));
```

```sql
CREATE VIEW sales_by_quarter AS
SELECT region,
       sum(amount) FILTER (WHERE quarter = 'Q1') AS q1,
       sum(amount) FILTER (WHERE quarter = 'Q2') AS q2,
       sum(amount) FILTER (WHERE quarter = 'Q3') AS q3
FROM sales
GROUP BY region;

DO $$
BEGIN
    ASSERT (SELECT q2 FROM sales_by_quarter WHERE region = 'north') = 200;
    ASSERT (SELECT q2 FROM sales_by_quarter WHERE region = 'south') IS NULL;
END $$;
```

The rules of the rewrite:

- every column of the pivot's source that is not in the aggregate and not
  in `FOR` becomes a `GROUP BY` column (here: `region`);
- every value in `IN (...)` becomes one aggregate with
  `FILTER (WHERE for_column = value)`, named by its alias;
- several aggregates in one `PIVOT` (`SUM(amount) AS s, COUNT(*) AS c`)
  give one column per value per aggregate: `sum(...) FILTER (...) AS q1_s`,
  `count(*) FILTER (...) AS q1_c`.

Like Oracle, a value with no rows gives `NULL`, not `0`; wrap it in
`coalesce(..., 0)` where a zero is wanted.

`PIVOT XML` and a dynamic `IN (ANY)` produce a column list that depends on
the data. SQL in PostgreSQL needs the columns known up front: build the
statement in PL/pgSQL with `format()` and `EXECUTE`, or return the pairs
as `jsonb` (`jsonb_object_agg(quarter, total)`) and let the client spread
them.

The `tablefunc` extension's `crosstab()` is the other well-known answer.
It works, but the column list still has to be written out in the call, and
it is easy to get wrong with missing values; `FILTER` is simpler and needs
no extension.

## UNPIVOT -> LATERAL VALUES

```plsql
SELECT region, quarter, amount
FROM sales_by_quarter
UNPIVOT (amount FOR quarter IN (q1 AS 'Q1', q2 AS 'Q2', q3 AS 'Q3'));
```

```sql
CREATE VIEW sales_unpivoted AS
SELECT s.region, v.quarter, v.amount
FROM sales_by_quarter s
CROSS JOIN LATERAL (
    VALUES ('Q1', s.q1), ('Q2', s.q2), ('Q3', s.q3)
) AS v(quarter, amount)
WHERE v.amount IS NOT NULL;   -- UNPIVOT's default is EXCLUDE NULLS

DO $$
BEGIN
    ASSERT (SELECT count(*) FROM sales_unpivoted) = 4;
    ASSERT (SELECT amount FROM sales_unpivoted WHERE region = 'south' AND quarter = 'Q3') = 120;
END $$;
```

`UNPIVOT INCLUDE NULLS` is the same query without the `WHERE`. Unpivoting
several columns at once (`UNPIVOT ((a, b) FOR ...)`) is the same `VALUES`
list with more columns per row.

## Watch out for

- **Types.** `UNPIVOT` requires the unpivoted columns to share a type, and
  so does `VALUES`. Cast where they differ (`s.q1::text`).
- **Implicit grouping.** `PIVOT` groups by *every* remaining column of its
  source. Pivoting straight from a wide table instead of a subquery
  silently adds all its columns to the grouping; in the rewrite, list the
  `GROUP BY` columns deliberately.
