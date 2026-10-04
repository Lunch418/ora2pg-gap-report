*English | [Русский](hierarchical-queries.ru.md)*

# Hierarchical queries: CONNECT BY -> WITH RECURSIVE

Covers: GAP-005 (`connect_by`), GAP-014 (`connect_by_nocycle`), GAP-024
(`recursive_with`), GAP-039 (`connect_by_pseudocolumn`).

## The problem

`ora2pg` turns a plain `CONNECT BY` into `WITH RECURSIVE`, but gets
`LEVEL` wrong (GAP-005), wrecks the surrounding block when `NOCYCLE` or
`ORDER SIBLINGS BY` is involved (GAP-014), leaves `CONNECT_BY_ROOT`,
`CONNECT_BY_ISLEAF` and `CONNECT_BY_ISCYCLE` as they are (GAP-039), and
copies a recursive `WITH` that Oracle runs without the `RECURSIVE` keyword
(GAP-024). Every one of these is one pattern in PostgreSQL: write the
recursion out by hand and carry what Oracle computes for you as columns.

The Oracle query this page rewrites:

```plsql
SELECT employee_id,
       LEVEL                               AS lvl,
       SYS_CONNECT_BY_PATH(last_name, '/') AS path,
       CONNECT_BY_ROOT last_name           AS root_name,
       CONNECT_BY_ISLEAF                   AS is_leaf
FROM employees
START WITH manager_id IS NULL
CONNECT BY PRIOR employee_id = manager_id
ORDER SIBLINGS BY last_name;
```

## The PostgreSQL pattern

```sql
CREATE TABLE employees (
    employee_id integer PRIMARY KEY,
    manager_id  integer REFERENCES employees,
    last_name   text NOT NULL
);
INSERT INTO employees VALUES
    (1, NULL, 'King'),
    (2, 1, 'Kochhar'),
    (3, 1, 'De Haan'),
    (4, 2, 'Greenberg'),
    (5, 3, 'Hunold'),
    (6, 4, 'Faviet');

CREATE VIEW employee_tree AS
WITH RECURSIVE tree AS (
    -- START WITH
    SELECT employee_id,
           manager_id,
           last_name,
           1                    AS lvl,        -- LEVEL
           '/' || last_name     AS path,       -- SYS_CONNECT_BY_PATH
           last_name            AS root_name,  -- CONNECT_BY_ROOT
           ARRAY[last_name]     AS sibling_key -- ORDER SIBLINGS BY
    FROM employees
    WHERE manager_id IS NULL
    UNION ALL
    -- CONNECT BY PRIOR employee_id = manager_id
    SELECT e.employee_id,
           e.manager_id,
           e.last_name,
           t.lvl + 1,
           t.path || '/' || e.last_name,
           t.root_name,
           t.sibling_key || e.last_name
    FROM employees e
    JOIN tree t ON e.manager_id = t.employee_id
)
SELECT employee_id,
       lvl,
       path,
       root_name,
       -- CONNECT_BY_ISLEAF
       NOT EXISTS (SELECT 1 FROM employees c WHERE c.manager_id = tree.employee_id) AS is_leaf,
       sibling_key
FROM tree;

SELECT employee_id, lvl, path, root_name, is_leaf
FROM employee_tree
ORDER BY sibling_key;  -- the whole ORDER SIBLINGS BY
```

What each part replaces:

| Oracle | PostgreSQL |
|---|---|
| `START WITH cond` | the first branch of the `UNION ALL` |
| `CONNECT BY PRIOR a = b` | the join in the second branch, `child.b = tree.a` |
| `LEVEL` | a counter column: `1`, then `parent + 1` |
| `SYS_CONNECT_BY_PATH(x, '/')` | a text column built the same way |
| `CONNECT_BY_ROOT x` | a column set in the first branch and copied down |
| `CONNECT_BY_ISLEAF` | `NOT EXISTS` a child row |
| `ORDER SIBLINGS BY x` | an array of `x` along the path, then `ORDER BY` that array |

The checks below run with the recipe in the test suite:

```sql
DO $$
BEGIN
    ASSERT (SELECT lvl FROM employee_tree WHERE employee_id = 6) = 4;
    ASSERT (SELECT path FROM employee_tree WHERE employee_id = 6) = '/King/Kochhar/Greenberg/Faviet';
    ASSERT (SELECT bool_and(root_name = 'King') FROM employee_tree);
    ASSERT (SELECT array_agg(employee_id ORDER BY employee_id) FROM employee_tree WHERE is_leaf) = ARRAY[5, 6];
    -- siblings in name order: De Haan's branch before Kochhar's
    ASSERT (SELECT array_agg(employee_id ORDER BY sibling_key) FROM employee_tree) = ARRAY[1, 3, 5, 2, 4, 6];
END $$;
```

`sibling_key` sorts by name only, like Oracle's `ORDER SIBLINGS BY
last_name`. If two siblings can share a name and the order between them
matters, append the key to the array as well, for example
`ARRAY[last_name || ':' || employee_id]`, or use an array of a composite
type.

## NOCYCLE and CONNECT_BY_ISCYCLE

A table with one parent per row cannot loop back to its root, so cycles
come from link tables. In Oracle, `CONNECT BY NOCYCLE` stops before a row
that would repeat, and `CONNECT_BY_ISCYCLE` is `1` on the row whose child
would close a loop. PostgreSQL 14 and later have the `CYCLE` clause for
the first half:

```sql
CREATE TABLE links (from_id integer, to_id integer);
INSERT INTO links VALUES (1, 2), (2, 3), (3, 1), (3, 4);

CREATE VIEW link_walk AS
WITH RECURSIVE walk AS (
    SELECT to_id AS node, 1 AS lvl
    FROM links
    WHERE from_id = 1
    UNION ALL
    SELECT l.to_id, w.lvl + 1
    FROM links l
    JOIN walk w ON l.from_id = w.node
) CYCLE node SET is_cycle USING visited
SELECT node,
       lvl,
       -- CONNECT_BY_ISCYCLE: a child of this row is already on its path
       EXISTS (
           SELECT 1 FROM links l
           WHERE l.from_id = walk.node
             AND ROW(l.to_id) = ANY (walk.visited)
       ) AS is_cycle_row
FROM walk
WHERE NOT is_cycle;  -- NOCYCLE: drop the row that repeats

DO $$
BEGIN
    ASSERT (SELECT array_agg(node ORDER BY lvl, node) FROM link_walk) = ARRAY[2, 3, 1, 4];
    ASSERT (SELECT array_agg(node ORDER BY node) FROM link_walk WHERE is_cycle_row) = ARRAY[1];
END $$;
```

`CYCLE node SET is_cycle USING visited` adds two columns: `is_cycle` is
true on the row that would repeat a node, and `visited` is the path as an
array of rows. Filtering `NOT is_cycle` gives the rows Oracle's `NOCYCLE`
returns.

Note that the start rows are the links *from* node 1, so node 1 itself
appears once the walk comes back to it; Oracle does the same when the
`START WITH` rows are links.

## A recursive WITH without RECURSIVE

Oracle 11gR2+ accepts a recursive subquery factoring clause without any
keyword. PostgreSQL needs `WITH RECURSIVE`, and that is the whole fix.
Oracle's own `SEARCH DEPTH FIRST BY ... SET` and `CYCLE ... SET ... TO ...
DEFAULT` clauses map to PostgreSQL 14's `SEARCH DEPTH FIRST BY ... SET` and
`CYCLE ... SET ... USING`:

```sql
WITH RECURSIVE numbers (n) AS (
    SELECT 1
    UNION ALL
    SELECT n + 1 FROM numbers WHERE n < 5
) SEARCH DEPTH FIRST BY n SET ordering
SELECT n FROM numbers ORDER BY ordering;
```

## Watch out for

- **Performance.** Oracle optimizes `CONNECT BY` internally. A recursive
  CTE joins once per level: index the join column (`manager_id` here).
- **Filters.** A `WHERE` in an Oracle hierarchical query applies *after*
  the hierarchy is built, but a condition inside `CONNECT BY` prunes
  whole branches. Put the first kind in the outer `SELECT` and the second
  in the recursive branch's `JOIN` condition.
- **`LEVEL` in `ora2pg` output.** If you keep the generated query instead
  of rewriting it, check every `LEVEL`: GAP-005 is exactly that column
  coming out wrong. `ora2pg-gap-report --check-connect-by` finds them.
