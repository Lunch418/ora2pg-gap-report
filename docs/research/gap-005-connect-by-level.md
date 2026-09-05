# GAP-005: `CONNECT BY` — a `LEVEL` substitution bug in the generated `WITH RECURSIVE`

Oracle feature: `START WITH ... CONNECT BY PRIOR ...` (hierarchical
queries) with `LEVEL`/`SYS_CONNECT_BY_PATH`.

## What is actually wrong here

Confirmed by a run against a synthetic fixture, honestly labelled as
synthetic (`hierarchy_demo_pkg`, a wrapper around the canonical Oracle
EMP/DEPT query inside a real package with a `REF CURSOR`). ora2pg **really
does convert** `START WITH ... CONNECT BY PRIOR ... SYS_CONNECT_BY_PATH`
into a working `WITH RECURSIVE` CTE:

```sql
WITH RECURSIVE cte AS (
SELECT employee_id,manager_id,1 AS depth,last_name AS org_path
      FROM   employees WHERE employee_id = p_top_employee_id
  UNION ALL
SELECT employee_id,manager_id,(c.level+1) AS depth,c.org_path || '/' || last_name AS org_path
      FROM   employees JOIN cte c ON (c.employee_id = manager_id)
) SELECT * FROM cte;
```

`LEVEL` has become a depth counter, `SYS_CONNECT_BY_PATH` string
concatenation, and `START WITH`/`CONNECT BY PRIOR` an anchor plus a
recursive join. Mechanically this is working SQL, and the cost is counted
correctly — the only one of the five originally examined classes where
`estimate_cost` does not understate.

The conversion is templated and brittle, though: `(c.level+1)` refers to a
`level` column the CTE does not have. This is a substitution bug in the
regex-based converter, which took the literal name `LEVEL` and failed to
substitute the `depth` alias from the first `UNION` branch. The generated
SQL will not run on PostgreSQL as written without a manual fix (`c.level`
→ `c.depth`). The converter also cannot handle the more complex variants:
`CONNECT BY NOCYCLE`, multiple conditions, `ORDER SIBLINGS BY`,
`CONNECT_BY_ROOT`, `CONNECT_BY_ISLEAF` — none of these are covered by any
regex in `PLSQL.pm`.

## Observed problem

`CONNECT BY` is the one class where the baseline cost estimate is not
understated. But the conversion itself is not error-free even for the
basic case — the value here is not "we see what ora2pg does not see at
all", it is "we warn that even with a non-zero estimated cost, the
generated SQL has to be read through by hand".

**Reproducible: YES.** Ora2Pg version: 25.0 (commit `cc2c434f`).

## Verdict

**Gap confirmed**, but atypical in mechanism: the only detector in the
project that analyses ora2pg's generated output rather than the original
Oracle source — and therefore the only one that needs `ora2pg` installed
to run (the `--check-connect-by` flag).

Implemented in `ora2pg_gap_report/detectors/connect_by.py`.
