# GAP-041: collection operators — `MULTISET`, `MEMBER OF`, `SUBMULTISET`

Oracle feature: treating nested tables and `VARRAY`s as sets directly in
SQL — union, intersection and difference of collections, membership
tests, subset tests, and the `CAST(MULTISET(SELECT ...) AS
<collection_type>)` idiom for collecting a subquery's result into a
collection.

## Minimal example

```sql
CREATE OR REPLACE VIEW v_multiset AS
SELECT id, col_a MULTISET UNION col_b AS merged
FROM basket_data
WHERE 5 MEMBER OF col_a;
```

## ora2pg output (v25.0, `-t VIEW`)

```sql
CREATE OR REPLACE VIEW v_multiset AS SELECT id, col_a MULTISET
UNION
 col_b AS merged
FROM basket_data
WHERE 5 MEMBER OF col_a;
```

Copied as written (ora2pg only moves the `UNION` onto its own line,
breaking the construct apart — it does not convert it).

## Observed problem

Confirmed against a real PostgreSQL 16:

```
ERROR:  syntax error at or near "col_b"
LINE 3:  col_b AS merged
         ^
```

Checked separately — every construct in this family behaves the same way
(copied verbatim, fails at load):

- `CAST(MULTISET(SELECT ...) AS num_list_t)` →
  `ERROR: syntax error at or near "SELECT"`
- `col_a SUBMULTISET OF col_b` →
  `ERROR: syntax error at or near "SUBMULTISET"`
- `MULTISET INTERSECT` — carried over verbatim in the same way.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/multiset_operator.py`. Manual rework onto
PostgreSQL's array model: `CAST(MULTISET(...))` → `ARRAY(SELECT ...)`,
`MULTISET UNION` → `||`, `MEMBER OF` → `= ANY(...)`, `SUBMULTISET OF` →
`<@`.

Kept separate from `collection_type` (GAP-021): that one is about
declaring a collection type (`CREATE TYPE ... AS TABLE OF`), this one
about operators over collection values in queries.
