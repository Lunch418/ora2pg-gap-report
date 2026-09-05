# GAP-048: `IGNORE NULLS` / `RESPECT NULLS` in analytic functions

Oracle feature: the null-treatment clause of analytic functions (`LAG`,
`LEAD`, `FIRST_VALUE`, `LAST_VALUE`, `NTH_VALUE`).

## Minimal example

```sql
SELECT emp_id,
       LAST_VALUE(salary IGNORE NULLS) OVER (PARTITION BY dept ORDER BY hired) AS last_sal,
       LAG(bonus, 1) IGNORE NULLS OVER (ORDER BY hired) AS prev_bonus
  FROM employees;
```

## ora2pg output (v25.0, `-t QUERY`)

```sql
SELECT emp_id,
       LAST_VALUE(salary IGNORE NULLS) OVER (PARTITION BY dept ORDER BY hired) AS last_sal,
       LAG(bonus, 1) IGNORE NULLS OVER (ORDER BY hired) AS prev_bonus
  FROM employees;
```

Copied as written.

## Observed problem

Confirmed against a real PostgreSQL 16 (the query was run against a real
`employees` table, so that a "relation does not exist" error could not
mask the real one):

```
ERROR:  syntax error at or near "IGNORE"
LINE 2:        LAST_VALUE(salary IGNORE NULLS) OVER (PARTITION BY de...
                                 ^
```

The `RESPECT NULLS` variant was checked separately — in Oracle that is the
default behaviour, but it can be written out explicitly. ora2pg copies it
into the output the same way, and PostgreSQL fails the same way:

```
ERROR:  syntax error at or near "RESPECT"
LINE 1: SELECT FIRST_VALUE(salary RESPECT NULLS) OVER (ORDER BY hire...
                                  ^
```

So the detector flags both forms, not only the "interesting" one.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/ignore_nulls.py`. Manual rework: PostgreSQL
16 has no direct syntax, so `IGNORE NULLS` is emulated — usually through a
grouping key built with `count(col) FILTER (WHERE col IS NOT NULL)` plus
`first_value` within the group, or through a lateral subquery.
