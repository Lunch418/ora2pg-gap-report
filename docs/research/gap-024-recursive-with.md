# GAP-024: a native recursive `WITH ... AS (...)` with no `RECURSIVE` keyword

Oracle feature: recursive subquery factoring — `WITH cte (cols) AS (anchor
UNION [ALL] recursive-branch)`, where the recursive branch references `cte`
itself. Not the same thing as `CONNECT BY` (see GAP-005): this is a
separate, modern, portable way of writing recursive queries, without
Oracle's hierarchical extensions. Oracle does not require an explicit
`RECURSIVE` keyword — the recursion is detected automatically from the
self-reference.

## Minimal example

```sql
WITH tree (employee_id, manager_id) AS (
    SELECT employee_id, manager_id FROM employees WHERE manager_id IS NULL
    UNION ALL
    SELECT e.employee_id, e.manager_id
    FROM employees e, tree t
    WHERE e.manager_id = t.employee_id
)
SELECT COUNT(*) INTO v_count FROM tree;
```

## ora2pg output (v25.0, `-t PACKAGE`)

```sql
WITH tree(employee_id, manager_id) AS (
    ...
)
SELECT COUNT(*)                     FROM tree
```

The `WITH` is copied as written — the `RECURSIVE` keyword is not added.

## Observed problem

Confirmed against a real PostgreSQL 16: `CREATE PROCEDURE` succeeds
without error and fails on the first call:

```
ERROR:  relation "tree" does not exist
DETAIL:  There is a WITH item named "tree", but it cannot be referenced
         from this part of the query.
HINT:  Use WITH RECURSIVE, or re-order the WITH items to remove forward
       references.
```

PostgreSQL requires the `RECURSIVE` keyword explicitly — without it the
CTE's self-reference in the second `UNION` branch does not resolve.

Checked separately: if the Oracle query additionally uses a `CYCLE` clause
(`WITH cte (...) CYCLE col SET flag TO 'Y' DEFAULT 'N' AS (...)` — the
clause sits before `AS`), simply adding `RECURSIVE` is not enough. In
PostgreSQL the `CYCLE` clause syntactically follows the closing
parenthesis of the CTE body rather than preceding `AS`, and requires a
mandatory `USING path_column` clause that the Oracle form does not have at
all. So for queries with `CYCLE` these are two overlapping, distinct
incompatibilities rather than one.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/recursive_with.py`. The detector looks for
`WITH name AS (` with no preceding `RECURSIVE`, where the body contains a
`UNION` and the CTE's name appears again in the `FROM` part of one of the
branches after that first `UNION` — which excludes both ordinary
non-recursive `UNION` CTEs and an accidental collision between a CTE name
and a column alias.
