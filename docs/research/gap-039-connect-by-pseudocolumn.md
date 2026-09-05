# GAP-039: `CONNECT_BY_ROOT` / `CONNECT_BY_ISLEAF` / `CONNECT_BY_ISCYCLE`

Oracle feature: the hierarchical operator and pseudocolumns used together
with `CONNECT BY` — the value of an expression at the root of the current
branch, a leaf flag, and a detected-cycle flag.

How this differs from GAP-005 (`connect_by`): that one is about the
`LEVEL` substitution bug in an already-generated `WITH RECURSIVE`. This is
about three separate constructs that ora2pg does not carry over at all.

## Minimal example

```sql
CREATE OR REPLACE VIEW v_emp_tree AS
SELECT employee_id,
       SYS_CONNECT_BY_PATH(last_name, '/') AS path,
       CONNECT_BY_ROOT last_name AS root_name,
       CONNECT_BY_ISLEAF AS is_leaf
FROM employees
START WITH manager_id IS NULL
CONNECT BY PRIOR employee_id = manager_id;
```

## ora2pg output (v25.0, `-t VIEW`)

```sql
CREATE OR REPLACE VIEW v_emp_tree AS WITH RECURSIVE cte AS (
SELECT employee_id,last_name AS path,CONNECT_BY_ROOT last_name AS root_name,CONNECT_BY_ISLEAF AS is_leaf
FROM employees WHERE coalesce(manager_id::text, '') = ''
  UNION ALL
SELECT employee_id,c.path || '/' || last_name AS path,CONNECT_BY_ROOT last_name AS root_name,CONNECT_BY_ISLEAF AS is_leaf
FROM employees JOIN cte c ON (c.employee_id = manager_id)

) SELECT * FROM cte;
```

`CONNECT BY` itself is expanded into `WITH RECURSIVE` correctly, and
`SYS_CONNECT_BY_PATH` is converted correctly too — into the concatenation
`c.path || '/' || last_name`. But `CONNECT_BY_ROOT` and
`CONNECT_BY_ISLEAF` are carried into the output verbatim.

## Observed problem

Confirmed against a real PostgreSQL 16:

```
ERROR:  syntax error at or near "AS"
LINE 2: ...ee_id,last_name AS path,CONNECT_BY_ROOT last_name AS root_na...
```

Checked separately (against a table that really exists, to tell a
construct error apart from a "no such table" error):

- `SYS_CONNECT_BY_PATH` **converts correctly on its own** — the error that
  remains on it is of a different kind and is not syntactic. The detector
  deliberately does NOT flag it. Details in "Side finding" below.
- `CONNECT_BY_ISCYCLE` behaves like `ISLEAF`: copied verbatim, and
  PostgreSQL answers `column "connect_by_iscycle" does not exist`.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/connect_by_pseudocolumn.py`. Manual rework:
the branch root is carried through as an extra column of the recursive
CTE, the leaf flag becomes a separate `NOT EXISTS` subquery, and the cycle
flag becomes the recursive CTE's `CYCLE` clause (PostgreSQL 14+).

## Side finding: unqualified columns in the generated CTE

While checking the boundary — what exactly breaks and what does not — a
separate, reproducible behaviour turned up that is not directly part of
this gap. In the recursive branch of the generated `WITH RECURSIVE`,
ora2pg leaves columns unqualified:

```sql
SELECT employee_id, c.path || '/' || last_name AS path
FROM employees JOIN cte c ON (c.employee_id = manager_id)
```

`employee_id` exists in both `employees` and `cte c`, so PostgreSQL 16
answers, against a table that really exists:

```
ERROR:  column reference "employee_id" is ambiguous
```

This is a bug in the **generated** code — the same category as GAP-005
(`connect_by`), which lints ora2pg's output and requires
`--check-connect-by`. It is deliberately not filed as a separate GAP: a
detector for it would have to work on the generated code rather than the
Oracle source, and its place is an extension of the existing `connect_by`
check rather than a new registry entry. Recorded here so the finding is
not lost.
