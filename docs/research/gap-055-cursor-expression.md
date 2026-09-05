# GAP-055: the cursor expression `CURSOR(SELECT ...)`

Oracle feature: a nested query returned as a separate cursor column, which
the client then opens and reads row by row.

## Minimal example

```sql
SELECT d.dname,
       CURSOR(SELECT e.name FROM employees e WHERE e.dept_id = d.id) AS emps
  FROM departments d;
```

## ora2pg output (v25.0, `-t QUERY`)

```sql
SELECT d.dname,
       CURSOR(SELECT e.name FROM employees e WHERE e.dept_id = d.id) AS emps
  FROM departments d;
```

Copied as written.

## Observed problem

Confirmed against a real PostgreSQL 16:

```
ERROR:  syntax error at or near "SELECT"
LINE 2:        CURSOR(SELECT e.name FROM employees e WHERE e.dept_id...
                      ^
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/cursor_expression.py`. The detector flags
only `CURSOR(` followed immediately by `SELECT` — an ordinary cursor
declaration (`CURSOR c IS SELECT ...`) is converted correctly by ora2pg
and is deliberately not flagged.

Manual rework: most often what was meant is a join with the child rows
aggregated into an array or json (`array_agg`, `json_agg`). If the client
really does read the nested set row by row, then a separate function
returning a `refcursor`.
