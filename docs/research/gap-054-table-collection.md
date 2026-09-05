# GAP-054: the `TABLE(...)` operator in `FROM`

Oracle feature: `TABLE(...)` expands a collection (a nested table, a
`VARRAY`, or the result of a pipelined function) into a set of rows
directly in `FROM`.

## Minimal example

```sql
SELECT t.column_value
  FROM TABLE(get_ids(42)) t;
```

## ora2pg output (v25.0, `-t QUERY`)

```sql
SELECT t.column_value
  FROM TABLE(get_ids(42)) t;
```

Copied as written.

## Observed problem

Confirmed against a real PostgreSQL 16:

```
ERROR:  syntax error at or near "TABLE"
LINE 2:   FROM TABLE(get_ids(42)) t;
               ^
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/table_collection.py`. The detector requires a
`FROM`/`JOIN`/`APPLY` keyword before `TABLE(`: the word `TABLE` is far too
common in SQL (`CREATE TABLE`, `ALTER TABLE`, `TRUNCATE TABLE`, `TYPE t IS
TABLE OF`), and without that anchor there would be more false positives
than real findings.

Manual rework: the nearest analogue is `unnest(...)` for an array, or an
ordinary set-returning function call in `FROM` (`FROM get_ids(42)`). But
the substitution is not mechanical: it depends on what the collection
itself became in PostgreSQL — an array, a separate table, or a function
returning `SETOF`. For the declarations of such types, see
GAP-021/`collection_type.py`.
