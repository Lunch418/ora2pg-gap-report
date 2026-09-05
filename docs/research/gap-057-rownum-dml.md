# GAP-057: `ROWNUM` in `UPDATE`/`DELETE` becomes `LIMIT`

Oracle feature: limiting the number of rows changed, through `WHERE ROWNUM
<= n`.

## Minimal example

```sql
UPDATE employees SET bonus = 0 WHERE ROWNUM <= 10;
```

## ora2pg output (v25.0, `-t QUERY`)

```sql
UPDATE employees SET bonus = 0 LIMIT 10;
```

Replacing `ROWNUM` with `LIMIT` is the right idea for a `SELECT`, but not
for DML.

## Observed problem

Confirmed against a real PostgreSQL 16:

```
ERROR:  syntax error at or near "LIMIT"
LINE 1: UPDATE employees SET bonus = 0 LIMIT 10;
                                       ^
```

The same for `DELETE`:

```sql
DELETE FROM employees WHERE ROWNUM <= 5;
```
```sql
DELETE FROM employees LIMIT 5;
```
```
ERROR:  syntax error at or near "LIMIT"
LINE 1: DELETE FROM employees LIMIT 5;
                              ^
```

**An important boundary for the detector.** `ROWNUM` inside a nested
subquery converts correctly and works — checked separately:

```sql
DELETE FROM employees WHERE emp_id IN (SELECT emp_id FROM staff WHERE ROWNUM <= 5);
```
```sql
DELETE FROM employees WHERE emp_id IN (SELECT emp_id FROM staff LIMIT 5);
```
```
DELETE 0
```

A `LIMIT` inside a subquery is perfectly ordinary PostgreSQL. So the
detector flags `ROWNUM` only when the nearest preceding statement keyword
is `UPDATE` or `DELETE` rather than `SELECT`. That is not a
just-in-case heuristic but a direct consequence of the measured behaviour.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/rownum_dml.py`. Manual rework: through a
subquery on the primary key — `DELETE FROM t WHERE id IN (SELECT id FROM t
WHERE ... LIMIT n)`. The meaning still changes: Oracle makes no promise
about which n rows `ROWNUM` picks, so the inner `SELECT` almost always
needs an explicit `ORDER BY` added, or the choice of rows stays
non-deterministic.
