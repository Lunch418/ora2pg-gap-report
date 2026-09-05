# GAP-066: `CREATE VIEW ... WITH READ ONLY`

Oracle feature: a view through which data cannot be changed —
`INSERT`/`UPDATE`/`DELETE` against it fail with ORA-42399.

## Minimal example

```sql
CREATE OR REPLACE VIEW v_emp AS
  SELECT emp_id, name FROM employees
  WITH READ ONLY;
```

## ora2pg output (v25.0, `-t VIEW`)

```sql
CREATE OR REPLACE VIEW v_emp AS SELECT emp_id, name FROM employees;
```

The clause is simply discarded.

## Observed problem

There is no error, at load or afterwards. A simple view in PostgreSQL is
automatically updatable by default, so a write through it silently
succeeds. Confirmed against a real PostgreSQL 16:

```
INSERT 0 1
 emp_id |               name
--------+----------------------------------
    999 | written through a READ ONLY view
(1 row)
```

The row really did reach the base table. The protection Oracle declared in
the object's own definition disappears without trace after migration —
this is `failure_stage = semantic`.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/read_only_view.py`. Manual rework: restore
the prohibition explicitly — either through privileges (`REVOKE INSERT,
UPDATE, DELETE ON <view> FROM ...`) or through an `INSTEAD OF` trigger
that raises an exception. The related gap for tables is
GAP-026/`read_only_table.py`.
