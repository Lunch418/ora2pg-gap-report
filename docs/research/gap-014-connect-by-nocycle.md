# GAP-014: `CONNECT BY NOCYCLE` / `ORDER SIBLINGS BY` — the block's structure is destroyed on conversion

Oracle feature: hierarchical-query extensions beyond plain `CONNECT BY`
(see GAP-005 for `CONNECT BY` itself and its known `LEVEL` bug) —
`NOCYCLE` (protection against cycles in the graph) and `ORDER SIBLINGS BY`
(ordering children within one parent while preserving the hierarchical
traversal order).

## Minimal example

```sql
CREATE OR REPLACE PROCEDURE build_tree AS
BEGIN
    FOR r IN (
        SELECT employee_id
        FROM employees
        START WITH manager_id IS NULL
        CONNECT BY NOCYCLE PRIOR employee_id = manager_id
        ORDER SIBLINGS BY employee_id
    ) LOOP
        NULL;
    END LOOP;
END;
/
```

## ora2pg output (v25.0, `-t PACKAGE`)

Unlike plain `CONNECT BY` — which becomes a `WITH RECURSIVE` inside the
function body, with its own separate `LEVEL` bug (GAP-005) — this
extension breaks the conversion far more seriously: the generated `WITH
RECURSIVE` ended up inserted **before** `DECLARE`, and the procedure body
came out with broken `DECLARE`/`CURSOR` nesting. The structure of the
whole block falls apart, not just the hierarchical query.

## Observed problem

Confirmed against a real PostgreSQL 16: `CREATE PROCEDURE` fails at the
function body's compilation stage (a syntax error), not merely on the
first call — that is, even earlier than for the typical gaps in this
registry, where `check_function_bodies = false` usually defers the error
to the first `CALL`.

This is not an inaccurate translation of one construct: it is structural
damage to the whole surrounding PL/SQL block, which makes rolling back or
repairing it harder than for the more localized gaps.

Checked separately: plain `CONNECT BY` with neither `NOCYCLE` nor `ORDER
SIBLINGS BY` is not flagged by this detector — it already has its own,
less serious gap (GAP-005 / `detectors/connect_by.py`).

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/connect_by_nocycle.py`. `CONNECT BY NOCYCLE`
and `ORDER SIBLINGS BY` are flagged separately, since a query may contain
either construct or both at once.
