# GAP-003: `BULK COLLECT` / `FORALL` / local nested-table `TYPE` declarations

Oracle feature: bulk operations — `TYPE ... IS TABLE OF ...%TYPE` (a
locally declared nested-table/associative-array collection type),
`BULK COLLECT INTO`, `FORALL`, and collection indexing (`v_ids(i)`,
`v_ids.COUNT`). Extremely common in real-world Oracle PL/SQL — this is the
standard idiom for bulk fetch/DML, used far more often than any of this
project's four existing detector targets.

## Minimal example

```sql
CREATE OR REPLACE PACKAGE BODY bulk_test_pkg AS
  PROCEDURE archive_old_orders IS
    TYPE t_id_tab IS TABLE OF orders.order_id%TYPE;
    v_ids t_id_tab;
  BEGIN
    SELECT order_id
    BULK COLLECT INTO v_ids
    FROM orders
    WHERE status = 'CLOSED';

    FORALL i IN 1 .. v_ids.COUNT
      DELETE FROM orders WHERE order_id = v_ids(i);

    COMMIT;
  END archive_old_orders;
END bulk_test_pkg;
/
```

## ora2pg output (v25.0, `-t PACKAGE`)

Essentially unconverted — Oracle syntax passed through as-is, with one
cosmetic change (`BULK COLLECT INTO` → `BULK COLLECT INTO STRICT`, which is
not a fix; `STRICT` is a PL/pgSQL `SELECT INTO` modifier unrelated to
`BULK COLLECT`). `TYPE t_id_tab IS TABLE OF ...%TYPE`, `FORALL`, and
`v_ids.COUNT`/`v_ids(i)` are left exactly as Oracle wrote them — none of
these are valid PL/pgSQL syntax.

## Observed problem

Confirmed against a real PostgreSQL 16 server. Unlike GAP-002, this fails
immediately — not on some later statement, but on the collection type
declaration itself, before the function body does anything at all:

```
ERROR:  syntax error at or near "IS"
LINE 4:     TYPE t_id_tab IS TABLE OF orders.order_id%TYPE;
                          ^
CONTEXT:  invalid type name "t_id_tab IS TABLE OF orders.order_id%TYPE"
```

Same silent-at-creation-time, fails-only-on-first-`CALL` behavior as
GAP-002 (`check_function_bodies = false` in ora2pg's output).

**Reproducible: YES.** Ora2Pg version: 25.0. PostgreSQL version: 16.

## Verdict

**Gap confirmed, and severe.** This isn't a narrow edge case like GAP-002 —
`BULK COLLECT`/`FORALL` is one of the most common Oracle PL/SQL
performance idioms, used in essentially every codebase that does batch
processing. A completely unconverted local collection `TYPE` declaration
means the containing routine won't even get past its `DECLARE` section.

This is likely the strongest detector in the project by practical impact —
stronger than any of the four that existed before it.

Detector implemented: `ora2pg_gap_report/detectors/bulk_collect.py` — a
source-level detector recognizing `TYPE ... IS TABLE OF` / `BULK COLLECT
INTO` / `FORALL` via `plsql_lex.py`'s masking infrastructure,
string/comment-aware, tested against real open-source fixtures (not just
this synthetic example — confirmed live on `docs/research/samples/logger.pkb`'s
own local collection type and on both compound-trigger fixtures).
