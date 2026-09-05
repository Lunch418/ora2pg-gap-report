# GAP-046: `CREATE BITMAP INDEX` → `USING gin` with no operator class

Oracle feature: a bitmap index, designed for low-cardinality columns and
for combining several such indexes with bitwise operations.

## Minimal example

```sql
CREATE TABLE emp_idx (
    employee_id NUMBER PRIMARY KEY,
    gender      VARCHAR2(1),
    last_name   VARCHAR2(50)
);
CREATE BITMAP INDEX idx_emp_gender ON emp_idx (gender);
CREATE INDEX idx_emp_rev ON emp_idx (last_name) REVERSE;
```

## ora2pg output (v25.0, `-t TABLE`)

```sql
CREATE TABLE emp_idx (
	employee_id bigint,
	gender varchar(1),
	last_name varchar(50)
) ;
CREATE INDEX idx_emp_gender ON emp_idx USING gin(gender);
CREATE INDEX idx_emp_rev ON emp_idx (last_name);
ALTER TABLE emp_idx ADD PRIMARY KEY (employee_id);
```

`BITMAP` has been replaced with `USING gin`.

## Observed problem

Confirmed against a real PostgreSQL 16 — the index is not created at all:

```
ERROR:  data type character varying has no default operator class for access method "gin"
HINT:  You must specify an operator class for the index or define a default operator class for the data type.
```

`gin` has no default operator class for `varchar` or for numeric types —
it is meant for composite types (arrays, `jsonb`, `tsvector`). So the
substitution does not merely change the index's characteristics: it fails
to load.

Noted separately (not raised as its own gap): a `REVERSE` index silently
loses its reversal and becomes an ordinary one.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/bitmap_index.py`. PostgreSQL has no bitmap
index as an index type. The practical replacement is a plain btree — the
planner combines several btrees through a bitmap scan at execution time
on its own — or `gin` with an explicit operator class from the
`btree_gin` extension.
