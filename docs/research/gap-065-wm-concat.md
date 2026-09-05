# GAP-065: `WM_CONCAT`

Oracle feature: an undocumented aggregate function that joins a group's
values into one comma-separated string. It was never officially supported
and was removed as of 12c, but it turns up constantly in legacy code.

## Minimal example

```sql
SELECT dept_id, WM_CONCAT(name) AS names FROM employees GROUP BY dept_id;
```

## ora2pg output (v25.0, `-t QUERY`)

```sql
SELECT dept_id, WM_CONCAT(name) AS names FROM employees GROUP BY dept_id;
```

Copied as written. By way of contrast, the same ora2pg rewrites the
documented `LISTAGG` into `string_agg` — checked in the same run:

```sql
SELECT dept, LISTAGG(name, ',') WITHIN GROUP (ORDER BY name) AS names ...
```
```sql
SELECT dept, string_agg(name, ',' ORDER BY name) AS names ...
```

## Observed problem

Confirmed against a real PostgreSQL 16 (against a real `employees` table):

```
ERROR:  function wm_concat(text) does not exist
LINE 1: SELECT dept_id, WM_CONCAT(name) AS names FROM employees GROU...
                        ^
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/wm_concat.py`. Manual rework: replace it with
`string_agg(col, ',')`, and add an explicit order while doing so —
`string_agg(col, ',' ORDER BY col)`. `WM_CONCAT` guaranteed no ordering at
all, so "as it was" cannot be reproduced anyway, and it is better to make
a silently non-deterministic result explicit.
